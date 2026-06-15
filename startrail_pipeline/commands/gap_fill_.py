from pathlib import Path

import numpy as np
from PIL import Image
import tifffile


def _shift_edge(array, dx, dy):
    height, width = array.shape
    pad_y = abs(dy)
    pad_x = abs(dx)
    padded = np.pad(array, ((pad_y, pad_y), (pad_x, pad_x)), mode="edge")
    y0 = pad_y - dy
    x0 = pad_x - dx
    return padded[y0:y0 + height, x0:x0 + width]


def directional_close(channel, dx, dy):
    offsets = ((-dx, -dy), (0, 0), (dx, dy))
    dilated = np.maximum.reduce(
        [_shift_edge(channel, offset_x, offset_y) for offset_x, offset_y in offsets]
    )
    return np.minimum.reduce(
        [_shift_edge(dilated, offset_x, offset_y) for offset_x, offset_y in offsets]
    )


def gap_fill_image(image, dx=1, dy=3, sky_fraction=0.9):
    if image.dtype != np.uint16 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Gap filling requires a 16-bit RGB image")
    result = image.copy()
    sky_height = max(1, min(image.shape[0], round(image.shape[0] * sky_fraction)))
    for channel_index in range(3):
        sky = image[:sky_height, :, channel_index]
        closed = directional_close(sky, dx, dy)
        result[:sky_height, :, channel_index] = np.maximum(sky, closed)
    return result


def cmd_gap_fill(args, log):
    source = Path(args.input)
    output = Path(args.output)
    if output.exists() and not args.force:
        raise RuntimeError(f"Output already exists: {output}. Pass --force to overwrite.")

    image = tifffile.imread(str(source))
    result = gap_fill_image(
        image,
        dx=args.dx,
        dy=args.dy,
        sky_fraction=args.sky_fraction,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(str(output), result, compression="zlib")

    preview_path = output.with_suffix(".jpg")
    Image.fromarray((result >> 8).astype(np.uint8), "RGB").save(
        preview_path, "JPEG", quality=92
    )
    changed = int(np.count_nonzero(result != image))
    log.info(
        f"Gap-filled {source} -> {output}; direction=({args.dx},{args.dy}), "
        f"changed channel values={changed}"
    )
