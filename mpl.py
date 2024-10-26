#!/usr/bin/python3

"""Simple and easy-to-use text-based program for launching mpv."""

from string import digits, punctuation, whitespace
from signal import signal, SIGCHLD, SIG_IGN
from subprocess import Popen, DEVNULL
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from shlex import split
import curses
import os

from natsort import natsorted

signal(SIGCHLD, SIG_IGN)  # Prevents the formation of zombie processes.

# Essential constants:
AUDIO_EXTS: tuple[str, ...] = ("aac", "flac", "m4a", "mp3", "ogg", "wav", "wma")
VIDEO_EXTS: tuple[str, ...] = ("avi", "iso", "mkv", "mov", "mp4", "webm", "wmv")
OTHER_EXTS: tuple[str, ...] = ("cue", "m3u", "m3u8")

SUB_EXTS: tuple[str, ...] = ("ass", "idx", "lrc", "srt", "sub", "vtt")

MPV_EXTENSIONS: tuple[str, ...] = (
    *AUDIO_EXTS,
    *VIDEO_EXTS,
    *OTHER_EXTS,
    *SUB_EXTS,
)

ENV_MPVL_MPV_CMD: str = os.getenv("MPVL_MPV_CMD", "mpv --force-window")
MPV_SUB_FILE_OPTION: str = "--sub-file="

IGNORED_NAMES: tuple[str, ...] = ("lost+found", ".git")  # Case-insensitive!

SPACE_CHAR: str = chr(32)  # for a bit more readable code...


def exec_nonblocking(cmd: str) -> int:
    """Creates a child process that does not block the parent process."""
    p = Popen(split(cmd), stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, start_new_session=True)
    return p.pid


def mpv_open(path: str, sub_path: str = ""):
    cmd: list[str] = [ENV_MPVL_MPV_CMD]
    if sub_path:
        cmd.append("".join((MPV_SUB_FILE_OPTION, '"', sub_path, '"')))
    cmd.append("".join(('"', path, '"')))
    return exec_nonblocking(SPACE_CHAR.join(cmd))


def fixed_len_slice(data: Sequence, max_len: int, offset: int = 0) -> Sequence:
    """A function that returns a slice of a given size from an indexable data type,
    considering the specified offset."""
    data_len: int = len(data)
    if data_len <= max_len:
        return data
    offset = max(0, min(offset, data_len - max_len))
    return data[offset : max_len + offset]


def search_by_words(term: str, text: str, split_char: str = SPACE_CHAR, case_sensitive: bool = False) -> bool:
    if not case_sensitive:
        term = term.casefold()
        text = text.casefold()
    term_set: set[str] = set(term.split(split_char))
    hit: int = 0
    for w in term_set:
        if w.strip(whitespace) in text:
            hit += 1
    return len(term_set) == hit


@dataclass
class FdItem:
    """Dataclass storing the properties of a broadly interpreted file element."""

    is_dir: bool
    name: str  # File name and extension as well.
    full: str  # Full path (includes the file name as well).
    size: int  # in bytes

    def get_ext(self, with_dot: bool = False) -> str:
        """Return extension."""
        _, ext = os.path.splitext(self.name)
        if with_dot:
            return ext
        return ext.lstrip(".")

    def is_hidden(self) -> bool:
        """Logical evaluation of whether it is a dotfile."""
        try:
            return self.name[0] == "."
        except IndexError:
            return False


class Navi:
    """Class used for navigation within the filesystem."""

    def __init__(self, current_dir: str = ".") -> None:
        """Set current directory."""
        self.current_dir_list: list[str] = []
        self.fd_list: list[FdItem] = []

        self.set_current_dir(current_dir)

    def discard_fd_list(self) -> None:
        """Deleting the contents of fd_list."""
        self.fd_list *= 0

    def refresh_fd_list(self) -> None:
        """Updating fd_list according to the current directory."""
        self.discard_fd_list()

        try:
            fd_temp: list[str] = natsorted(os.listdir(self.get_current_dir()))
        except PermissionError:
            return
        except FileNotFoundError:
            return
        except NotADirectoryError:
            return

        for item in fd_temp:
            if item in IGNORED_NAMES:
                continue

            full: str = os.path.join(self.get_current_dir(), item)
            item_stat: os.stat_result = os.stat(full)
            self.fd_list.append(FdItem(is_dir=os.path.isdir(full), name=item, full=full, size=item_stat.st_size))

    def get_current_dir(self) -> str:
        """Retrieving the path of the current directory."""
        return os.path.abspath(os.path.join(*self.current_dir_list))

    def set_current_dir(self, current_dir: str) -> None:
        """Replaces the current directory value if the specified path points to a directory."""
        if os.path.isdir(current_dir):
            self.current_dir_list = [current_dir]

    def cd(self, name: str) -> None:
        """Change directory."""
        name = name.strip("/")
        if name == ".":
            return
        self.current_dir_list.append(name)

    def up(self) -> None:
        """Navigating to the parent directory."""
        self.cd("..")


class NaviFiltered(Navi):
    """x"""

    def __init__(self, current_dir: str = ".") -> None:
        """x"""
        Navi.__init__(self, current_dir)

        self.fd_list_filtered: list[FdItem] = []

        self.filter_show_dirs: bool = True
        self.filter_show_hidden: bool = False
        self.filter_exts: tuple[str, ...] = ()
        self.filter_text: str = ""

    def discard_fd_list_filtered(self) -> None:
        """x"""
        self.fd_list_filtered *= 0

    def toggle_filter_show_dirs(self) -> bool:
        """x"""
        self.filter_show_dirs = not self.filter_show_dirs
        return self.filter_show_dirs

    def toggle_filter_show_hidden(self) -> bool:
        """x"""
        self.filter_show_hidden = not self.filter_show_hidden
        return self.filter_show_hidden

    def set_filter_exts(self, exts: tuple[str, ...]) -> None:
        """x"""
        self.filter_exts = exts

    def set_filter_text(self, text: str) -> None:
        """x"""
        self.filter_text = text

    def get_filter_text(self) -> str:
        """x"""
        return self.filter_text

    def discard_filter_text(self) -> None:
        """x"""
        self.filter_text *= 0

    def refresh_fd_list_filtered(self) -> None:
        """x"""
        self.discard_fd_list_filtered()

        for item in self.fd_list:
            if not self.filter_show_dirs and item.is_dir:
                continue
            if not self.filter_show_hidden and item.is_hidden():
                continue
            if self.filter_exts and not item.is_dir and item.get_ext() not in self.filter_exts:
                continue
            if self.filter_text and not search_by_words(self.filter_text, item.name):
                continue

            self.fd_list_filtered.append(item)

    def get_index_by_name(self, name: str) -> int:
        """x"""
        i: int = -1
        for c, item in enumerate(self.fd_list_filtered):
            if name == item.name:
                i = c
                break
        return i


class App:
    """x"""

    UNUSED_LINES: int = 3
    LIST_START: int = 1

    def __init__(self, last_item_file: str) -> None:
        self.window = curses.initscr()
        self.window.keypad(True)
        curses.curs_set(0)
        curses.noecho()
        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, -1, -1)  # default
        # (1) Blue    -> directory
        # (2) Yellow  -> audio
        # (3) Green   -> video
        # (4) Magenta -> subtitles
        # (5) Cyan    -> last_item
        try:
            curses.init_pair(2, 12, -1)
            curses.init_pair(3, 11, -1)
            curses.init_pair(4, 10, -1)
            curses.init_pair(5, 13, -1)
            curses.init_pair(6, 14, -1)
        except ValueError:
            curses.init_pair(2, 4, -1)
            curses.init_pair(3, 3, -1)
            curses.init_pair(4, 2, -1)
            curses.init_pair(5, 5, -1)
            curses.init_pair(6, 6, -1)

        self.refresh_sizes()

        self.cursor: int = 0
        self.offset: int = 0

        self.last_item_file = last_item_file
        self.last_item: str = ""
        try:
            self.last_item = Path(self.last_item_file).read_text().strip()
        except FileNotFoundError:
            pass

        self.navi_filtered = NaviFiltered()
        self.navi_filtered.set_filter_exts(MPV_EXTENSIONS)
        if not self.restore_last_item():
            self.navi_filtered.refresh_fd_list()
            self.navi_filtered.refresh_fd_list_filtered()

        self.current_message: str = ""
        self.pids: list[int] = []
        self.sub_path: str = ""

    def restore_last_item(self) -> bool:
        if os.path.isfile(self.last_item):
            self.navi_filtered.set_current_dir(os.path.dirname(self.last_item))
            self.navi_filtered.refresh_fd_list()
            self.navi_filtered.refresh_fd_list_filtered()
            self.set_cursor(self.navi_filtered.get_index_by_name(os.path.basename(self.last_item)))
            return True
        return False

    def save_last_item(self) -> None:
        Path(self.last_item_file).write_text(self.last_item)

    def refresh_sizes(self) -> None:
        curses.update_lines_cols()
        self.avail_lines: int = curses.LINES - self.UNUSED_LINES
        self.avail_lines_i: int = self.avail_lines - 1

    def reset_index(self) -> None:
        self.cursor, self.offset = 0, 0

    def get_index(self) -> int:
        return self.cursor + self.offset

    def get_cursor_item(self) -> FdItem:
        return self.navi_filtered.fd_list_filtered[self.get_index()]

    def draw(self) -> None:
        self.window.erase()

        # Status line:
        status_line: list[str] = [self.navi_filtered.get_current_dir()]
        if not self.navi_filtered.fd_list_filtered:
            status_line.append("[EMPTY]")
        if self.sub_path:
            status_line.append("[SUB]")
        pids_num: int = len(self.pids)
        if pids_num:
            status_line.append("[mpv:{}]".format(str(pids_num)))
        if not self.navi_filtered.filter_show_dirs:
            status_line.append("(NO DIR.)")
        if self.navi_filtered.filter_show_hidden:
            status_line.append("(HIDDEN)")
        self.window.addstr(0, 0, str(fixed_len_slice((2 * SPACE_CHAR).join(status_line), curses.COLS, 1000)))

        # List:
        line_num: int = self.LIST_START
        for i, item in enumerate(fixed_len_slice(self.navi_filtered.fd_list_filtered, self.avail_lines, self.offset)):
            name: str = item.name
            ext: str = item.get_ext()
            style: int = curses.color_pair(1)

            if item.is_dir:
                name = "".join((name, "/"))
                style = curses.color_pair(2)
            elif item.full == self.last_item:
                style = curses.color_pair(6)
            elif ext in AUDIO_EXTS:
                style = curses.color_pair(3)
            elif ext in VIDEO_EXTS:
                style = curses.color_pair(4)
            elif ext in SUB_EXTS:
                style = curses.color_pair(5)
            else:
                pass

            if i == self.cursor:
                style = style | curses.A_REVERSE

            self.window.addstr(line_num, 0, str(fixed_len_slice(name, curses.COLS)), style)

            line_num += 1

        # Message line:
        self.window.addstr(curses.LINES - 2, 0, str(fixed_len_slice(self.current_message, curses.COLS)))

        # Name filter input:
        try:
            self.window.addstr(
                curses.LINES - 1,
                0,
                str(fixed_len_slice("".join((":", self.navi_filtered.get_filter_text())), curses.COLS, 1000)),
            )
        except curses.error:
            pass

        self.window.refresh()

    def choose(self, with_save: bool = False) -> None:
        try:
            item = self.get_cursor_item()
        except IndexError:  # A typical case when the list is empty.
            return

        if item.is_dir:
            self.navi_filtered.cd(item.name)
            self.navi_filtered.discard_filter_text()
            self.navi_filtered.refresh_fd_list()
            self.navi_filtered.refresh_fd_list_filtered()
            self.reset_index()
        else:
            ext: str = item.get_ext()
            if ext in SUB_EXTS:
                if not self.sub_path:  # empty string
                    self.sub_path = item.full
                    self.current_message = "Subtitle selected: {}".format(item.name)
                else:  # not empty, but needs to be deleted. (toggle-like)
                    self.sub_path *= 0
                    self.current_message = "No subtitle selected."
                return

            if ext == "iso":  # Requires a different command.
                return

            self.pids.append(mpv_open(item.full, self.sub_path))

            if with_save:
                self.last_item = item.full
                self.save_last_item()
                self.current_message = "Saved for later playback: {}".format(item.name)

    def input_down(self) -> None:
        if self.get_index() == len(self.navi_filtered.fd_list_filtered) - 1:
            return

        self.cursor += 1
        if self.cursor > self.avail_lines_i:
            self.cursor = self.avail_lines_i
            self.offset += 1

    def input_up(self) -> None:
        if not self.get_index():
            return

        self.cursor -= 1
        if self.cursor < 0:
            self.cursor = 0
            self.offset -= 1

    def set_cursor(self, index: int) -> None:
        list_i = len(self.navi_filtered.fd_list_filtered) - 1
        if index < 0 or index > list_i:
            return

        # First page:
        if 0 <= index <= self.avail_lines_i:
            self.cursor = index
            self.offset = 0
            return

        # Last page:
        lastpage_first_i = list_i - self.avail_lines_i
        if (lastpage_first_i + 2) <= index <= list_i:
            self.cursor = self.avail_lines_i - (list_i - index)
            self.offset = index - self.cursor
            return

        # To the middle:
        self.cursor = self.avail_lines // 2
        rema: int = self.avail_lines - self.cursor
        self.offset = index - rema
        if self.cursor != rema:
            self.offset += 1

    def input(self) -> bool:
        wch = self.window.get_wch()
        if wch == curses.KEY_RESIZE:
            self.refresh_sizes()
            self.reset_index()
        elif wch == curses.KEY_DOWN:
            self.input_down()
        elif wch == curses.KEY_UP:
            self.input_up()
        elif wch == curses.KEY_LEFT:
            prev_dirname = os.path.basename(self.navi_filtered.get_current_dir())
            self.navi_filtered.up()
            self.navi_filtered.discard_filter_text()
            self.navi_filtered.filter_show_dirs = True
            self.navi_filtered.refresh_fd_list()
            self.navi_filtered.refresh_fd_list_filtered()
            self.set_cursor(self.navi_filtered.get_index_by_name(prev_dirname))
        elif wch == curses.KEY_RIGHT:
            self.choose()
        elif wch in (curses.KEY_ENTER, "\n"):
            self.choose(with_save=True)
        elif wch == curses.KEY_F5:
            self.current_message *= 0
            self.navi_filtered.refresh_fd_list()
            self.navi_filtered.refresh_fd_list_filtered()
        elif wch == curses.KEY_F6:
            self.navi_filtered.toggle_filter_show_dirs()
            self.navi_filtered.refresh_fd_list_filtered()
            self.reset_index()
        elif wch == curses.KEY_F7:
            self.navi_filtered.toggle_filter_show_hidden()
            self.navi_filtered.refresh_fd_list_filtered()
            self.reset_index()
        elif wch == curses.KEY_F8:
            self.restore_last_item()
        elif wch == curses.KEY_F9:
            pass
        elif wch == curses.KEY_F11:
            pass
        elif wch == curses.KEY_F12:  # exit
            return True
        elif wch == curses.KEY_BACKSPACE:
            self.navi_filtered.set_filter_text(self.navi_filtered.get_filter_text()[:-1])
            self.navi_filtered.refresh_fd_list_filtered()
        elif wch in (curses.KEY_DC, curses.KEY_DL):
            self.navi_filtered.discard_filter_text()
            self.navi_filtered.refresh_fd_list_filtered()
        else:
            wch_str = str(wch)

            if wch_str.isalpha() or wch_str == SPACE_CHAR or wch_str in tuple(digits) or wch_str in tuple(punctuation):
                self.navi_filtered.set_filter_text("".join((self.navi_filtered.get_filter_text(), wch_str)))
                self.navi_filtered.refresh_fd_list_filtered()
                self.reset_index()

        return False

    def loop(self) -> None:
        while 1:
            self.draw()
            if self.input():
                break

    def run(self) -> None:
        try:
            self.loop()
        except KeyboardInterrupt:
            pass
        finally:
            curses.endwin()


# Basic variables:
WORK_DIR: str = os.path.join(os.path.expanduser("~"), ".local", "state", "mpl")
LAST_ITEM_FILE: str = os.path.join(WORK_DIR, "last_item")

if __name__ == "__main__":
    if not os.path.exists(WORK_DIR):
        os.makedirs(WORK_DIR, 0o744)

    app = App(LAST_ITEM_FILE)
    app.run()
