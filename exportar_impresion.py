"""Export a reviewed book using printer-provided cover dimensions."""
import argparse
from pathlib import Path
from kdp.print_package import export_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('book', type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--spine', required=True, type=float, help='Spine in inches from printer calculator')
    parser.add_argument('--width', required=True, type=float, help='Full cover width in inches')
    parser.add_argument('--height', required=True, type=float, help='Full cover height in inches')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(export_package(args.book,args.config,spine=args.spine,cover_width=args.width,
                             cover_height=args.height,destination=args.out))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')

if __name__ == '__main__':
    main()
