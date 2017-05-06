"""
Small addon for blender to help with rendering in VSE.
It automates rendering with multiple instances of blender.

Copyright (c) 2017 Krzysztof Trzcinski
"""

from bpy import types
from bpy.props import EnumProperty
from bpy.props import IntProperty
from bpy.props import PointerProperty
from collections import namedtuple
from multiprocessing import cpu_count
from multiprocessing.dummy import Pool
from queue import Queue
from threading import Thread
from threading import Lock
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

class WorkerProcess(object):
    @staticmethod
    def read_config():
        config = json.load(sys.stdin)
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.connect(tuple(config['controller']))
        return MessageChannel(sck), config['args']

    def __init__(self, args):
        self._args = args
        self._sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sck.bind(('localhost', 0))
        self._sck.listen(1)
        self._p = None
        self._incoming = None

    def __enter__(self):
        cmd = (
            bpy.app.binary_path,
            bpy.data.filepath,
            '--background',
            '--python',
            __file__,
        )

        self._p = subprocess.Popen(cmd, stdin = subprocess.PIPE)

        config = {
            'controller': self._sck.getsockname(),
            'args': self._args
        }

        #json.dump(config, self._p.stdin)
        self._p.stdin.write(json.dumps(config).encode('utf8'))
        self._p.stdin.close()

        conn, _addr = self._sck.accept()
        return MessageChannel(conn)

    def __exit__(self, exc_t, exc_v, tb):
        pass

    def wait(self):
        return self._p.wait()

class ParallelRender(types.Operator):
    """Object Cursor Array"""
    bl_idname = "render.parallel_render"
    bl_label = "Parallel Render"
    bl_options = {'REGISTER'}

    batch_type = EnumProperty(
        items = [
            # (identifier, name, description, icon, number)
            ('parts', 'No. parts', 'Render in given number of batches (automatically splits it)'),
            ('fixed', 'Fixed', 'Render in fixed size batches'), 
        ],
        name = "Render Batch Size"
    )

    fixed = IntProperty(
        name = "Number of frames per batch",
        min = 1,
        default = 300,
        max = 10000
    )

    parts = IntProperty(
        name = "Number of batches",
        min = 1,
        default = cpu_count() * 2,
        max = 10000
    )

    max_parallel = IntProperty(
        name = "Maximum number of instances",
        min = 1,
        default = cpu_count() // 2,
        max = 10000
    )

    still_running = False
    thread = None 
    state = None

    def draw(self, context):
        layout = self.layout
        if bpy.data.is_dirty:
            layout.label("You have unsaved changes.", text_ctxt="Render will be done with last saved version", icon='ERROR')

        layout.prop(self, "max_parallel")

        layout.prop(self, "batch_type", expand=True)
        sub_prop = str(self.batch_type)
        if hasattr(self, sub_prop):
            layout.prop(self, sub_prop)

    def check(self, context):
        return True

    def _get_ranges_parts(self, scn):
        start = scn.frame_start - 1
        end = scn.frame_end
        length = end - start 
        parts = int(self.parts)

        if length <= parts:
            yield (start + 1, end)
            return

        for i in range(1, parts + 1):
            end = i * length // parts
            yield (start + 1, end)
            start = end

    def _get_ranges_fixed(self, scn):
        start = scn.frame_start
        end = scn.frame_end
        increment = int(self.fixed)
        while start <= end:
            yield (start, min(start + increment, end))
            start += increment + 1

    def _run(self, scn):
        make_ranges = getattr(self, '_get_ranges_{0}'.format(str(self.batch_type)))
        ranges = tuple(make_ranges(scn))

        cmds = tuple(
            (
                (start, end),
                {
                    '--scene': str(scn.name),
                    '--start-frame': start,
                    '--end-frame': end,
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
        self.summary_mutex = Lock()

        RunResult = namedtuple('RunResult', ('range', 'command', 'rc'))

        def run(args):
            rng, cmd = args
            res = None

            if self.state == 'Running':
                try:
                    worker = WorkerProcess(cmd)
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
                    res = worker.wait()
                except Exception as exc:
                    LOGGER.exception(exc)
                    res = -1
            return RunResult(rng, cmd, res)

        self.state = 'Running'
        self.report({'INFO'}, 'Starting 0/{0} [0.0%]'.format(
            len(cmds)
        ))

        with Pool(int(self.max_parallel)) as pool:
            pending = pool.imap_unordered(run, cmds)
            results = {}
            for num, res in enumerate(pending, 1):
                with self.summary_mutex:
                    self.summary['batches_done'] = num
                results[res.range] = res
                self._report_progress()
                if any(res.rc not in (0, None) for res in results.values()):
                    self.state = 'Failed'
                
            self._report_progress()
            for rng, res in results.items():
                print(rng, res.rc)

    def _report_progress(self):
        rep_type, action = {
            'Running': ('INFO', 'Completed'),
            'Failed': ('ERROR', 'Failed'),
            'Cancelling': ('WARNING', 'Cancelling'),
        }[self.state]

        with self.summary_mutex:
            self.report({rep_type}, '{0} Batches: {1}/{2} Frames: {3}/{4} [{5:.1f}%]'.format(
                action,
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
        self.thread = Thread(target=self._run, args=(scn,))
        self.thread.start()
        return{'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager

        # Stop the thread when ESCAPE is pressed.
        if event.type == 'ESC':
            self.state = 'Cancelling'
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
        return wm.invoke_props_dialog(self)
    
def render_panel(self, context):
    scn = context.scene
    self.layout.prop(types.RenderSettings, 'parallel_render') 

def register():
    bpy.utils.register_module(__name__)

def unregister():
    bpy.utils.unregister_module(__name__)
    types.RENDER_PT_render.remove(render_panel)

def parse_args(args):
    argv = iter(sys.argv[start_pos+1:])
    argv = dict(zip(argv, argv))


def render():
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

            bpy.app.handlers.render_stats.append(send_stats)
            bpy.ops.render.render(animation=True, scene = scn_name)

            channel.send({
                'current_frame': scn.frame_end,
            })
        finally:
            channel.send(None)
    sys.exit(0)

if __name__ == "__main__":
    render()

