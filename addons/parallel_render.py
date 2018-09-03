"""
Small addon for blender to help with rendering in VSE.
It automates rendering with multiple instances of blender.

It should come up as "VSE Parallel Render" in addons list.

Copyright (c) 2017 Krzysztof Trzcinski
"""

from bpy import props
from bpy import types
from collections import namedtuple
from enum import Enum
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool
from queue import Queue
from threading import Lock
from threading import Thread
import bpy
import json
import logging
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time

LOGGER = logging.getLogger(__name__)

bl_info = {
    "name": "VSE parallel render",
    "category": "VSE"
}

class ParallelRenderPanel(bpy.types.Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "Parallel Render"
    bl_idname = "OBJECT_PT_parallel_render"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render"

    def draw(self, context):
        layout = self.layout

        layout.operator('render.parallel_render', icon='RENDER_ANIMATION')

        file_format = context.scene.render.image_settings.file_format
        can_run = file_format in {'FFMPEG', 'XVID', 'THEORA', 'AVI_RAW', 'H264', 'AVI_JPEG'}
        if not can_run:
            layout.enabled = False
            layout.label('Not available for render file format `{}`'.format(file_format), icon='ERROR')
            return

        addon_props = context.user_preferences.addons[__name__].preferences
        props = context.scene.parallel_render_panel

        layout.prop(props, "max_parallel")

        layout.prop(props, "overwrite")
        layout.prop(props, "batch_type", expand=True)
        sub_prop = str(props.batch_type)
        if hasattr(props, sub_prop):
            layout.prop(props, sub_prop)

        layout.prop(props, "mixdown")

        sub = layout.row()
        sub.prop(props, "concatenate")

        if addon_props.ffmpeg_valid:
            sub = layout.row()
            sub.prop(props, "clean_up_parts")
            sub.enabled = props.concatenate
        else:
            sub.enabled = False
            sub.label('Check add-on settings', icon='ERROR')

class MessageChannel(object):
    MSG_SIZE_FMT = '!i'
    MSG_SIZE_SIZE = struct.calcsize(MSG_SIZE_FMT)

    def __init__(self, conn):
        self._conn = conn

    def send(self, msg):
        msg = json.dumps(msg).encode('utf8')
        msg_size = len(msg)
        packed_size = struct.pack(self.MSG_SIZE_FMT, msg_size)
        self._conn.sendall(packed_size)
        self._conn.sendall(msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_t, exc_v, tb):
        self._conn.close()

    def _recv(self, size):
        buf = b''
        while len(buf) < size:
            read = self._conn.recv(size - len(buf))
            if len(read) == 0:
                raise Exception('Unexpected end of connection')
            buf += read
        return buf

    def recv(self):
        msg_size_packed = self._recv(self.MSG_SIZE_SIZE)
        msg_size = struct.unpack(self.MSG_SIZE_FMT, msg_size_packed)[0]
        if msg_size == 0:
            return None
        return json.loads(self._recv(msg_size).decode('utf8'))

class CurrentProjectFile(object):
    def __init__(self):
        self.path = None

    def __enter__(self):
        self.path = bpy.data.filepath
        return self
    
    def __exit__(self, exc_type, exc_value, tb):
        self.path = None

class TemporaryProjectCopy(object):
    def __init__(self):
        self.path = None

    def __enter__(self):
        project_file = tempfile.NamedTemporaryFile(
            delete=False,
            # Temporary project files has to be in the
            # same directory to ensure relative paths work.
            dir=bpy.path.abspath("//"),
            prefix='parallel_render_copy_{}_'.format(os.path.splitext(os.path.basename(bpy.data.filepath))[0]),
            suffix='.blend',
        )
        project_file.close()
        try:
            self.path = project_file.name

            bpy.ops.wm.save_as_mainfile(
                filepath=self.path,
                copy=True,
                check_existing=False,
                relative_remap=True,
            )

            assert os.path.exists(self.path)
            return self
        except:
            self._cleanup()
            raise

    def __exit__(self, exc_type, exc_value, tb):
        self._cleanup()

    def _cleanup(self):
        os.unlink(self.path)
        self._cleanup_autosave_files()

    def _cleanup_autosave_files(self):
        # TODO: Work out proper way to clean up .blend{n} files
        try:
            n = 1
            while True:
                os.unlink(self.path + str(n))
                n += 1
        except OSError:
            pass 

class WorkerProcess(object):
    @staticmethod
    def read_config():
        config = json.load(sys.stdin)
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.connect(tuple(config['controller']))
        return MessageChannel(sck), config['args']

    def __init__(self, args, project_file):
        self._args = args
        self._sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sck.bind(('localhost', 0))
        self._sck.listen(1)
        self._p = None
        self._incoming = None
        self._project_file = project_file

    def __enter__(self):
        cmd = (
            bpy.app.binary_path,
            self._project_file,
            '--background',
            '--python',
            __file__,
        )

        self._p = subprocess.Popen(cmd, stdin = subprocess.PIPE)

        config = {
            'controller': self._sck.getsockname(),
            'args': self._args
        }

        self._p.stdin.write(json.dumps(config).encode('utf8'))
        self._p.stdin.close()

        # This is rather arbitrary.
        # It is meant to protect accept() from hanging in case
        # something very wrong happens to launched process.
        self._sck.settimeout(30)

        conn, _addr = self._sck.accept()

        return MessageChannel(conn)

    def __exit__(self, exc_t, exc_v, tb):
        pass

    def wait(self):
        return self._p.wait()

def _add_multiline_label(layout, lines, icon='NONE'):
    for line in lines:
        row = layout.row()
        row.alignment = 'CENTER'
        row.label(line, icon=icon)
        icon='NONE'

def _is_valid_ffmpeg_executable(path):
    if not os.path.exists(path):
        return "Path `{}` does not exist".format(path)
    if not os.path.isfile(path):
        return "Path `{}` is not a file".format(path)
    if not os.access(path, os.X_OK):
        return "Path `{}` is not executable".format(path)

class ParallelRenderPreferences(types.AddonPreferences):
    bl_idname = __name__

    ffmpeg_executable = props.StringProperty(
        name="Path to ffmpeg executable",
        default="",
        update=lambda self, context: self.update(context),
        subtype='FILE_PATH',
    )

    ffmpeg_status = props.StringProperty(default="")
    ffmpeg_valid = props.BoolProperty(default=False)

    def update(self, context):
        error = _is_valid_ffmpeg_executable(self.ffmpeg_executable)
        if error is None:
            self.ffmpeg_valid = True
            info = subprocess.check_output((self.ffmpeg_executable, '-version')).decode('utf-8')
            self.ffmpeg_status = 'Version: {}'.format(info)
        else:
            self.ffmpeg_valid = False
            self.ffmpeg_status = error
            context.scene.parallel_render_panel.update(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ffmpeg_executable")
        icon = 'INFO' if self.ffmpeg_valid else 'ERROR'
        layout.label(self.ffmpeg_status, icon=icon)

def _need_temporary_file(data):
    return data.is_dirty

def parallel_render_menu_draw(self, context):
    layout = self.layout
    layout.operator('render.parallel_render', icon='RENDER_ANIMATION')
    layout.separator()

class ParallelRenderPropertyGroup(types.PropertyGroup):
    def update(self, context):
        addon_props = context.user_preferences.addons[__name__].preferences

        if not addon_props.ffmpeg_valid and self.concatenate:
            self.concatenate = False
            self.clean_up_parts = False

        if not self.concatenate:
            self.clean_up_parts = False

    batch_type = props.EnumProperty(
        items = [
            # (identifier, name, description, icon, number)
            ('parts', 'No. parts', 'Render in given number of batches (automatically splits it)'),
            ('fixed', 'Fixed', 'Render in fixed size batches'), 
        ],
        name = "Render Batch Size"
    )

    max_parallel = props.IntProperty(
        name = "Number of background worker Blender instances",
        min = 1,
        default = cpu_count() - 1,
        max = 10000
    )

    overwrite = props.BoolProperty(
        name = "Overwrite existing files",
        default = True,
    )

    mixdown = props.BoolProperty(
        name = "Mixdown sound",
        default = True,
    )

    concatenate = props.BoolProperty(
        name = "Concatenate output files into one",
        update = lambda self, context: self.update(context),
    )

    clean_up_parts = props.BoolProperty(
        name = "Clean up partial files (after successful concatenation)",
    )

    fixed = props.IntProperty(
        name = "Number of frames per batch",
        min = 1,
        default = 300,
        max = 10000
    )

    parts = props.IntProperty(
        name = "Number of batches",
        min = 1,
        default = cpu_count() * 2,
        max = 10000
    )

class ParallelRenderState(Enum):
    CLEANING = 1
    RUNNING = 2
    MIXDOWN = 3
    CONCATENATE = 4
    FAILED = 5
    CANCELLING = 6

    def describe(self):
        return {
            self.CLEANING: ('INFO', 'Cleaning Up'),
            self.RUNNING: ('INFO', 'Rendering'),
            self.MIXDOWN: ('INFO', 'Mixing Sound'),
            self.CONCATENATE: ('INFO', 'Concatenating'),
            self.FAILED: ('ERROR', 'Failed'),
            self.CANCELLING: ('WARNING', 'Cancelling'),
        }[self]



class ParallelRender(types.Operator):
    """Object Cursor Array"""
    bl_idname = "render.parallel_render"
    bl_label = "Parallel Render"
    bl_options = {'REGISTER'}

    still_running = False
    thread = None 
    state = None

    def draw(self, context):
        layout = self.layout
        if _need_temporary_file(bpy.data):
            _add_multiline_label(
                layout,
                [
                    'Unsaved changes to project.',
                    'Will attempt to create temporary file.',
                ],
                icon='ERROR',
            )

        layout.row().label('Will render frames from {} to {}'.format(context.scene.frame_start, context.scene.frame_end))

    def __init__(self):
        super(ParallelRender, self).__init__()
        self.summary_mutex = None

    def check(self, context):
        return True

    def _get_ranges_parts(self, scn):
        offset = scn.frame_start
        current = 0
        end = scn.frame_end - offset
        length = end + 1
        parts = int(scn.parallel_render_panel.parts)

        if length <= parts:
            yield (scn.frame_start, scn.frame_end)
            return

        for i in range(1, parts + 1):
            end = i * length // parts
            yield (offset + current, offset + end - 1)
            current = end

    def _get_ranges_fixed(self, scn):
        start = scn.frame_start
        end = scn.frame_end
        increment = int(scn.parallel_render_panel.fixed)
        while start <= end:
            yield (start, min(start + increment, end))
            start += increment + 1

    def _render_project_file(self, scn, project_file):
        self.summary_mutex = Lock()

        props = scn.parallel_render_panel

        make_ranges = getattr(self, '_get_ranges_{0}'.format(str(props.batch_type)))
        ranges = tuple(make_ranges(scn))

        cmds = tuple(
            (
                (start, end),
                {
                    '--scene': str(scn.name),
                    '--start-frame': start,
                    '--end-frame': end,
                    '--overwrite': bool(props.overwrite),
                }
            )
            for start, end in ranges
        )

        self.summary = {
            'batches': len(cmds),
            'batches_done': 0,
            'frames': max(s[1] for s in ranges) - min(s[0] for s in ranges) + 1,
            'frames_done': 0,
        }
        RunResult = namedtuple('RunResult', ('range', 'command', 'rc', 'output_file'))

        self.report({'INFO'}, 'Working on file {0}'.format(project_file))

        def run(args):
            rng, cmd = args
            res = None
            output_file = None

            if self.state == ParallelRenderState.RUNNING:
                try:
                    worker = WorkerProcess(cmd, project_file=project_file)
                    msg = None
                    with worker as channel:
                        msgs = iter(channel.recv, None)
                        last_done = rng[0]
                        for msg in msgs:
                            frame_done = msg['current_frame']
                            with self.summary_mutex:
                                self.summary['frames_done'] += (frame_done - last_done)
                            last_done = frame_done

                        with self.summary_mutex:
                            self.summary['frames_done'] += 1
                    if msg is not None:
                        status_msg = 'Worker finished writing {}'.format(msg['output_file'])
                        output_file = msg['output_file']
                    LOGGER.info(status_msg)
                    print(status_msg)
                    res = worker.wait()
                except Exception as exc:
                    LOGGER.exception(exc)
                    res = -1
            return RunResult(rng, cmd, res, output_file)

        self.state = ParallelRenderState.RUNNING
        self.report({'INFO'}, 'Starting 0/{0} [0.0%]'.format(
            len(cmds)
        ))

        with Pool(props.max_parallel) as pool:
            pending = pool.imap_unordered(run, cmds)
            results = {}
            for num, res in enumerate(pending, 1):
                with self.summary_mutex:
                    self.summary['batches_done'] = num
                results[res.range] = res
                self._report_progress()
                if any(res.rc not in (0, None) for res in results.values()):
                    self.state = ParallelRenderState.FAILED
                
            self._report_progress()

        sound_path = os.path.splitext(bpy.context.scene.render.frame_path())[0] + '.mp3'
        if self.state == self.state.RUNNING and props.mixdown:
            self.state = ParallelRenderState.MIXDOWN
            with self.summary_mutex:
                self.report({'INFO'}, 'Mixing down sound')
                bpy.ops.sound.mixdown(filepath = sound_path)
            self._report_progress()
            self.state = ParallelRenderState.RUNNING

        if self.state == ParallelRenderState.RUNNING and props.concatenate:
            self.state = ParallelRenderState.CONCATENATE
            self.report({'INFO'}, 'Concatenating')
            concatenate_files = tempfile.NamedTemporaryFile(delete=False, mode = 'wt')
            with concatenate_files as data:
                for range, res in sorted(results.items()):
                    data.write("file '{}'\n".format(res.output_file))

            outfile = bpy.context.scene.render.frame_path()

            sound = ()
            if props.mixdown:
                sound = ('-i', sound_path, '-codec:a', 'copy', '-q:a', '0')

            overwrite = ('-y' if bool(props.overwrite) else '-n',)

            base_cmd = (
                self.ffmpeg_executable,
                '-nostdin',
                '-f', 'concat',
                '-safe', '0',
                '-i', concatenate_files.name,
                '-codec:v', 'copy',
                outfile,
            )

            cmd = base_cmd + sound + overwrite

            print(cmd)

            res = subprocess.call(cmd)
            if res == 0:
                self.state = self.state.RUNNING
            else:
                self.state = self.state.FAILED

        if self.state == ParallelRenderState.RUNNING and props.clean_up_parts:
            self.state = ParallelRenderState.CLEANING
            os.unlink(concatenate_files.name)
            os.unlink(sound_path)
            for res in results.values():
                os.unlink(res.output_file)
            self.state = ParallelRenderState.RUNNING

    def _run(self, scn):
        if _need_temporary_file(bpy.data):
            work_project_file = TemporaryProjectCopy()
        else:
            work_project_file = CurrentProjectFile()

        with work_project_file:
            self._render_project_file(scn, work_project_file.path)

    def _report_progress(self):
        rep_type, action = self.state.describe()
        with self.summary_mutex:
            self.report({rep_type}, '{0} Batches: {1}/{2} Frames: {3}/{4} [{5:.1f}%]'.format(
                action.replace('ing', 'ed'),
                self.summary['batches_done'],
                self.summary['batches'],
                self.summary['frames_done'],
                self.summary['frames'],
                100.0 * self.summary['frames_done'] / self.summary['frames']
            ))
        
    def execute(self, context):
        scn = context.scene
        wm = context.window_manager
        self.timer = wm.event_timer_add(0.5, context.window)
        wm.modal_handler_add(self)
        wm.progress_begin(0., 100.)

        addon_props = context.user_preferences.addons[__name__].preferences

        self.max_parallel = scn.parallel_render_panel.max_parallel
        self.ffmpeg_executable = addon_props.ffmpeg_executable

        self.thread = Thread(target=self._run, args=(scn,))
        self.thread.start()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if self.summary_mutex is None:
            return {'PASS_THROUGH'}

        wm = context.window_manager

        # Stop the thread when ESCAPE is pressed.
        if event.type == 'ESC':
            self.state = ParallelRenderState.CANCELLING
            self._report_progress()

        if event.type == 'TIMER':
            still_running = self.thread.is_alive() 
            with self.summary_mutex:
                percent = 100.0 * self.summary['batches_done'] / self.summary['batches']

            if still_running:
                wm.progress_update(percent)
                self._report_progress()
                return {'PASS_THROUGH'}

            self.thread.join()
            wm.event_timer_remove(self.timer)
            wm.progress_end()
            return {'FINISHED'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        wm = context.window_manager
        if not bpy.context.scene.render.is_movie_format:
            popup = wm.popup_menu(
                lambda op, context: (
                    op.layout.label("This feature is not supported."),
                    op.layout.label("Render output format has to be a movie type."),

                ),
                title='Image output is not supported',
                icon='CANCEL',
            )
            return {'FINISHED'}

        return wm.invoke_props_dialog(self)

def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.parallel_render_panel = bpy.props.PointerProperty(type=ParallelRenderPropertyGroup)
    # TODO: I am not quite sure how to put it after actual "Render Animation"
    bpy.types.INFO_MT_render.prepend(parallel_render_menu_draw)

def unregister():
    bpy.types.INFO_MT_render.remove(parallel_render_menu_draw)
    del bpy.types.Scene.parallel_render_panel
    bpy.utils.unregister_module(__name__)

def render():
    assert bpy.context.scene.render.is_movie_format

    channel, args = WorkerProcess.read_config()
    with channel:
        def send_stats(what):
            channel.send({
                'current_frame': bpy.context.scene.frame_current,
            })

        try:
            scn_name = args['--scene']
            scn = bpy.data.scenes[scn_name]
            scn.frame_start = args['--start-frame']
            scn.frame_end = args['--end-frame']

            outfile = bpy.context.scene.render.frame_path()
            LOGGER.info("Writing file {}".format(outfile))
            if args['--overwrite'] or not os.path.exists(outfile):
                bpy.app.handlers.render_stats.append(send_stats)
                bpy.ops.render.render(animation=True, scene = scn_name)
            else:
                print('{0} alread exists.'.format(outfile))

            channel.send({
                'current_frame': scn.frame_end,
                'output_file': outfile,
            })
            LOGGER.info("Done writing {}".format(outfile))
        finally:
            channel.send(None)
    sys.exit(0)

if __name__ == "__main__":
    render()

