#!/usr/bin/python3

from rshell import pyboard
pyb = pyboard.Pyboard("/dev/ttyACM0")


import os
import sys
import errno

from fuse import FUSE, FuseOSError, Operations, fuse_get_context

import stat

import json
import base64
import rshell

def rcall(cmd):
	pyb.exec('import os')
	pyb.exec('import ujson')
	return json.loads(pyb.eval('ujson.dumps(%s)' % cmd))

def rcall_bin(cmd):
	pyb.exec('import os')
	pyb.exec('import ujson')
	pyb.exec('import ubinascii')
	return base64.decodebytes(bytes(
		json.loads(
			pyb.eval('ujson.dumps([ubinascii.b2a_base64(%s)])' % cmd)
		)[0],
	"ascii"))

class UPFS(Operations):
	def __init__(self):
		self.fds = set()
		self.cache = {}

	# Helpers
	# =======

	def _get_new_fd(self):
		i = 3
		while i in self.fds:
			i += 1
		self.fds.add(i)
		return i

	def invalidate_cache(self, path):
		try:
			del self.cache[path]
		except KeyError:
			pass

	# Filesystem methods
	# ==================

	def access(self, path, mode):
		print("access: %s, %r" % (path, mode))
		#we have access to everything
		#but if we wouldn't, we would do this:
		#raise FuseOSError(errno.EACCES)

	def chmod(self, path, mode):
		self.invalidate_cache(path)
		print("ignoring chmod: %s: %o" % (path, mode))

	def chown(self, path, uid, gid):
		self.invalidate_cache(path)
		print("ignoring chown: %s: %i / %i" % (path, uid, gid))

	def getattr(self, path, fh=None):
		print("getattr: %s (%r)" % (path, fh))
		if path in self.cache:
			if self.cache[path] == errno.ENOENT:
				raise FuseOSError(errno.ENOENT)
			return self.cache[path]
		"""
		   S_IFSOCK   0140000   socket
           S_IFLNK    0120000   symbolic link
           S_IFREG    0100000   regular file
           S_IFBLK    0060000   block device
           S_IFDIR    0040000   directory
           S_IFCHR    0020000   character device
           S_IFIFO    0010000   FIFO
		"""
		try:
			st = rcall("os.stat(%r)" % path)
			st[0] |= 0o755
			if st[0] & stat.S_IFDIR:
				st[6] = 4096
			#if st[0] & stat.S_IFDIR:
			#	st[0] |= 0o755
			#else:
			#	st[0] |= 0o644
			a = {
				'st_mode': st[0],
				# st_ino
				# st_dev
				'st_uid': os.getuid(),
				'st_gid': os.getgid(),
				'st_nlink': st[5],
				'st_size': st[6],
				#FIXME: calculate wrong localtime?
				'st_atime': st[7],
				'st_mtime': st[8],
				'st_ctime': st[9],
			}
			self.cache[path] = a
			return a
		except rshell.pyboard.PyboardError:
			#pass
			#raise FuseOSError(errno.EACCES)
			self.cache[path] = errno.ENOENT
			raise FuseOSError(errno.ENOENT)

	def readdir(self, path, fh):
		print("readdir %s" % path)

		dirents = ['.', '..']
		#if os.path.isdir(full_path):
		#	dirents.extend(os.listdir(full_path))
		try:
			entries = rcall("os.listdir(%r)" % path)
			print(entries)
			dirents.extend(entries)
		except:
			return []

		for r in dirents:
			yield r

	def readlink(self, path):
		print("readlink %s" % path)
		raise FuseOSError(errno.EINVAL)
		"""
		pathname = os.readlink(self._full_path(path))
		if pathname.startswith("/"):
			# Path name is absolute, sanitize it.
			return os.path.relpath(pathname, self.root)
		else:
			return pathname
		"""

	def mknod(self, path, mode, dev):
		print("mknod: %s" % path)
		self.invalidate_cache(path)
		raise FuseOSError(errno.EINVAL)

	def rmdir(self, path):
		print("rmdir: %s" % path)
		self.invalidate_cache(path)
		pyb.exec("os.rmdir(%r)" % path)

	def mkdir(self, path, mode):
		print("mkdir: %s" % path)
		self.invalidate_cache(path)
		pyb.exec("os.mkdir(%r)" % path)

	def statfs(self, path):
		print("statfs: %s" % path)
		stv = rcall("os.statvfs(%r)" % path)
		"""
		   struct statvfs {
               unsigned long  f_bsize;    /* Filesystem block size */
               unsigned long  f_frsize;   /* Fragment size */
               fsblkcnt_t     f_blocks;   /* Size of fs in f_frsize units */
               fsblkcnt_t     f_bfree;    /* Number of free blocks */
               fsblkcnt_t     f_bavail;   /* Number of free blocks for
                                             unprivileged users */
               fsfilcnt_t     f_files;    /* Number of inodes */
               fsfilcnt_t     f_ffree;    /* Number of free inodes */
               fsfilcnt_t     f_favail;   /* Number of free inodes for
                                             unprivileged users */
               unsigned long  f_fsid;     /* Filesystem ID */
               unsigned long  f_flag;     /* Mount flags */
               unsigned long  f_namemax;  /* Maximum filename length */
           };
		"""
		return {
			'f_bsize': stv[0],
			'f_frsize': stv[1],
			'f_blocks': stv[2],
			'f_bfree': stv[3],
			'f_bavail': stv[4],
			'f_files': stv[5],
			'f_ffree': stv[6],
			'f_favail': stv[7],
			'f_flag': stv[8],
			'f_namemax': stv[9],
		}

	def unlink(self, path):
		print("unlink: %s" % path)
		self.invalidate_cache(path)
		pyb.exec('os.remove(%r)' % path)

	def symlink(self, name, target):
		print("symlink: %s" % path)
		self.invalidate_cache(path)
		raise FuseOSError(errno.EINVAL)

	def rename(self, old, new):
		print("rename: %s" % path)
		self.invalidate_cache(path)
		pyb.exec('os.rename(%r, %r)' % (old, new))

	def link(self, target, name):
		print("link: %s" % path)
		self.invalidate_cache(path)
		raise FuseOSError(errno.EINVAL)

	def utimens(self, path, times=None):
		print("ignoring utimens: %s" % path)
		self.invalidate_cache(path)
		#return os.utime(self._full_path(path), times)

	# File methods
	# ============

	def open(self, path, flags):
		self.invalidate_cache(path)
		print("open: %r" % path)
		print("%x" % flags)
		sf = ""
		if flags & os.O_APPEND:
			sf = 'a'
		elif flags & os.O_WRONLY:
			sf = 'w'
		elif (flags & os.O_RDONLY) == os.O_RDONLY:
			sf = 'r'
		sf += "b"
		if flags & os.O_RDWR:
			sf += "+"
		try:
			fd = self._get_new_fd()
			print("upfs_fd_%i = open(%r, %r)" % (fd, path, sf))
			pyb.exec("upfs_fd_%i = open(%r, %r)" % (fd, path, sf))
		except Exception as e:
			print(e)
			raise FileNotFoundError()
		return fd

	def create(self, path, mode, fi=None):
		self.invalidate_cache(path)
		print("create: %r: %r" % (path, mode))
		fd = self._get_new_fd()
		sf = "wb"
		print("upfs_fd_%i = open(%r, %r)" % (fd, path, sf))
		pyb.exec("upfs_fd_%i = open(%r, %r)" % (fd, path, sf))
		return fd

	def read(self, path, length, offset, fd):
		print("read: %r (%i, %i)" % (path, length, offset))
		self.invalidate_cache(path)
		pyb.exec("upfs_fd_%i.seek(%i)" % (fd, offset))
		# transfer in small chunks due to limited memory on device
		r = b""
		chunk_size = 8192
		for i in range(0, length, chunk_size):
			bytes_to_transfer = min(chunk_size, length-i)
			print("upfs_fd_%i.read(%i)" % (fd, bytes_to_transfer))
			r += rcall_bin("upfs_fd_%i.read(%i)" % (fd, bytes_to_transfer))
		#print("%r" % r)
		return r

	def write(self, path, buf, offset, fd):
		print("write %r: %r, %i" % (path, buf, offset))
		self.invalidate_cache(path)
		bb = base64.encodebytes(buf)
		pyb.exec('import ubinascii')
		pyb.exec("upfs_fd_%i.seek(%i)" % (fd, offset))
		pyb.exec("upfs_fd_%i.write(ubinascii.a2b_base64(%r))" % (fd, bb))
		return len(buf)

	def truncate(self, path, length, fd=None):
		print("truncate %r" % path)
		self.invalidate_cache(path)
		tfd = self._get_new_fd()
		pyb.exec("upfs_fd_%i = open(%r, 'rb')" % (tfd, path))
		r = rcall_bin("upfs_fd_%i.read(%i)" % (tfd, length))
		print(r)
		bb = base64.encodebytes(r)
		if not fd:
			pyb.exec("upfs_fd_%i = open(%r, 'wb')" % (tfd, path))
			fd = tfd
		pyb.exec('import ubinascii')
		pyb.exec("upfs_fd_%i.seek(0)" % fd)
		pyb.exec("upfs_fd_%i.write(ubinascii.a2b_base64(%r))" % (fd, bb))
		#if fd == tfd:
		#	pyb.exec("upfs_fd_%i.flush()" % tfd)
		pyb.exec("del upfs_fd_%i" % tfd)
		self.fds.remove(tfd)

	def flush(self, path, fd):
		print("flush %r" % path)
		self.invalidate_cache(path)
		pyb.exec("upfs_fd_%i.flush()" % fd)

	def release(self, path, fd):
		print("release: %r" % path)
		self.invalidate_cache(path)
		print("del upfs_fd_%i" % fd)
		pyb.exec("del upfs_fd_%i" % fd)
		self.fds.remove(fd)

	def fsync(self, path, fdatasync, fd):
		print("fsync %r" % path)
		self.invalidate_cache(path)
		pyb.exec("upfs_fd_%i.flush()" % fd)


def main(mountpoint):
	pyb.enter_raw_repl()
	u = UPFS()
	FUSE(u, mountpoint, nothreads=True, foreground=True)
	pyb.exit_raw_repl()


if __name__ == '__main__':
	main(sys.argv[1])
