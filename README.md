> [!WARNING]
> Moved to https://codeberg.org/asdil12/upfs

# Micropython FUSE filesystem

This tool allows to mount the storage of a micropython device via FUSE.
It communicates via the python raw REPL console with the device.

The filesystem doesn't support symlinks or hardlinks.

## Usage

```
./upfs.py /dev/ttyACM0 ./mountdir/
```
