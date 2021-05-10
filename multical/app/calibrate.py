from multical.app.common import get_paths
from multical.motion.static_frames import StaticFrames
from multical.motion.rolling_frames import RollingFrames
from multical.optimization.calibration import select_threshold
from multical.io.logging import setup_logging
from multical import board, workspace
from multical.io.logging import info

from .arguments import add_calibration_args, parse_with
from .vis import visualize_ws

from structs.struct import struct, map_none

from os import path
import pathlib
import numpy as np


def init_boards(args):
  assert args.boards is None or path.isfile(args.boards), f"board file {args.boards} not found"

  board_file = args.boards or path.join(args.image_path, "boards.yaml")
  calico_file = path.join(args.image_path, "../network_specification_file.txt")
  boards = {}

  if path.isfile(board_file):
    boards = board.load_config(board_file)
  elif path.isfile(calico_file):
    boards = board.load_calico(calico_file)      # CALICO board specification file
  else:
    assert False, f"no boards found, use --boards or add boards.yaml to image path"
  
  info("Using boards:")
  for name, b in boards.items():
    info(f"{name} {b}")  
  return boards

def initialise(args, paths, camera_images):
    ws = workspace.Workspace()
 
    setup_logging(args.log_level, [ws.log_handler], log_file=paths.log_file)
    info(args) 

    boards = init_boards(args)
 
    ws.load_images(j=args.j)
    ws.detect_boards(boards, cache_file=paths.detection_cache, 
      load_cache=not args.no_cache, j=args.j)
    
    ws.calibrate_single(args.distortion_model, fix_aspect=args.fix_aspect, 
      has_skew=args.allow_skew, max_images=args.intrinsic_images)

    motion_model = None
    if args.motion_model == "rolling":
      motion_model = RollingFrames
    elif args.motion_model == "static":
      motion_model = StaticFrames
    else:
      assert False, f"unknown motion model {args.motion_model}, (static|rolling)"

    ws.initialise_poses(motion_model=motion_model)
    return ws

def optimize(args, ws):

    outliers =  select_threshold(quantile=0.75, factor=args.outlier_threshold) 
    auto_scale = select_threshold(quantile=0.75, factor=args.auto_scale)\
      if args.auto_scale is not None else None

    ws.calibrate("calibration", loss=args.loss,  
      boards=args.adjust_board,
      cameras=not args.fix_intrinsic,
      camera_poses=not args.fix_camera_poses,
      board_poses=not args.fix_board_poses,
      motion=not args.fix_motion,
      auto_scale=auto_scale, outliers=outliers)


def calibrate(args): 
    np.set_printoptions(precision=4, suppress=True)

    paths = get_paths(args.output_path or args.image_path)
 
    cameras = map_none(str.split, args.cameras, ",")
    camera_images = find_camera_images(args.image_path, cameras, args.camera_pattern, master = args.master)
 
    ws = initialise(args, paths, camera_images)
    optimize(args, ws)

    ws.export(paths.export_file)
    ws.dump(paths.workspace_file)

    if args.vis:
      visualize_ws(ws)


if __name__ == '__main__':
    args = parse_with(add_calibration_args)
    calibrate(args)
