"""
Entry point for tests.
To run:

PYTHONPATH=tests python3.6 tests/parallel_render.py test <path to blender> <path to ffmpeg executable>

"""
from itertools import product
from time import sleep
from unittest import mock
import logging
import os
import shutil
import struct
import subprocess
import sys
import unittest

BLENDER_EXECUTABLE = None
LOGGER = logging.getLogger('tests_runtime')

class BlenderTest(unittest.TestCase):
    FFMPEG_EXECUTABLE = None

    def setUp(self):
        import bpy
        bpy.ops.wm.read_factory_settings()
        self.assertEqual(bpy.ops.wm.addon_enable(module='parallel_render'), {'FINISHED'})
        self.assertEqual(bpy.ops.script.reload(), {'FINISHED'})
        # Now that we have coverage enabled reload modules
        # to go through load/unload functions
        LOGGER.info('bpy.utls.script_paths: %s', bpy.utils.script_paths())
        LOGGER.info('cwd: %s', os.getcwd())

        self.bpy = bpy

class MessageChannelTest(BlenderTest):
    def test_unexpected_end(self):
        import parallel_render
        conn = mock.MagicMock()

        channel = parallel_render.MessageChannel(conn)
        with self.assertRaises(Exception):
            channel.recv()

        conn.recv.side_effect = [struct.pack(channel.MSG_SIZE_FMT, 0), None]
        self.assertEqual(channel.recv(), None)

class TemporaryProjectTest(BlenderTest):
    @mock.patch('os.path.exists')
    def test_temporary_project_file(self, exists):
        import parallel_render
        exists.return_value = False
        with self.assertRaises(Exception):
            with parallel_render.TemporaryProjectCopy() as test: pass

class RangesTest(BlenderTest):
    def test_parts(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.parts = 4
        scene.frame_start = 12
        scene.frame_end = 134

        self.assertEqual(
            [
                (12, 41),
                (42, 72),
                (73, 103),
                (104, 134),
            ],
            list(parallel_render.get_ranges_parts(scene)),
        )

    def test_tiny_parts(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.parts = 4
        scene.frame_start = 8
        scene.frame_end = 11

        self.assertEqual(
            [
                (8, 11),
            ],
            list(parallel_render.get_ranges_parts(scene)),
        )

    def test_small_parts(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.parts = 4
        scene.frame_start = 8
        scene.frame_end = 13

        self.assertEqual(
            [
                (8, 8),
                (9, 10),
                (11, 11),
                (12, 13),
            ],
            list(parallel_render.get_ranges_parts(scene)),
        )

    def test_fixed(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.fixed = 31
        scene.frame_start = 12
        scene.frame_end = 134

        self.assertEqual(
            [
                (12, 43),
                (44, 75),
                (76, 107),
                (108, 134),
            ],
            list(parallel_render.get_ranges_fixed(scene)),
        )

    def test_exact_fixed(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.fixed = 31
        scene.frame_start = 25
        scene.frame_end = 25+30

        self.assertEqual(
            [
                (25, 55),
            ],
            list(parallel_render.get_ranges_fixed(scene)),
        )

    def test_small_fixed(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.fixed = 31
        scene.frame_start = 25
        scene.frame_end = 25+31

        self.assertEqual(
            [
                (25, 56),
            ],
            list(parallel_render.get_ranges_fixed(scene)),
        )

    def test_fixed_9(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.fixed = 9
        scene.frame_start = 1
        scene.frame_end = 100

        self.assertEqual(
            [
                (1, 10),
                (11, 20),
                (21, 30),
                (31, 40),
                (41, 50),
                (51, 60),
                (61, 70),
                (71, 80),
                (81, 90),
                (91, 100),
            ],
            list(parallel_render.get_ranges_fixed(scene)),
        )

    def test_small2_fixed(self):
        import parallel_render

        scene = mock.MagicMock()
        scene.parallel_render_panel.fixed = 31
        scene.frame_start = 25
        scene.frame_end = 25+32

        self.assertEqual(
            [
                (25, 56),
                (57, 57),
            ],
            list(parallel_render.get_ranges_fixed(scene)),
        )


class MockedDrawTest(BlenderTest):
    def test_parallel_render_panel_draw(self):
        import parallel_render
        panel = mock.MagicMock()
        context = mock.MagicMock()

        addon_props = context.user_preferences.addons['parallel_render'].preferences

        for is_dirty in (True, False):
            with mock.patch('bpy.data') as data:
                data.is_dirty = is_dirty

                context.scene.render.is_movie_format = False
                addon_props.ffmpeg_valid = True
                parallel_render.ParallelRenderPanel.draw(panel, context)
                parallel_render.ParallelRender.check(panel, context)
                parallel_render.ParallelRender.draw(panel, context)
                parallel_render.ParallelRenderPreferences.draw(panel, context)
                parallel_render.parallel_render_menu_draw(panel, context)

                context.scene.render.is_movie_format = True
                addon_props.ffmpeg_valid = True
                parallel_render.ParallelRenderPanel.draw(panel, context)
                parallel_render.ParallelRender.draw(panel, context)
                parallel_render.ParallelRender.check(panel, context)
                parallel_render.ParallelRenderPreferences.draw(panel, context)
                parallel_render.parallel_render_menu_draw(panel, context)

                context.scene.render.is_movie_format = True
                addon_props.ffmpeg_valid = False
                parallel_render.ParallelRenderPanel.draw(panel, context)
                parallel_render.ParallelRender.draw(panel, context)
                parallel_render.ParallelRender.check(panel, context)
                parallel_render.ParallelRenderPreferences.draw(panel, context)
                parallel_render.parallel_render_menu_draw(panel, context)

                context.scene.render.is_movie_format = False
                addon_props.ffmpeg_valid = False
                parallel_render.ParallelRenderPanel.draw(panel, context)
                parallel_render.ParallelRender.draw(panel, context)
                parallel_render.ParallelRender.check(panel, context)
                parallel_render.ParallelRenderPreferences.draw(panel, context)
                parallel_render.parallel_render_menu_draw(panel, context)

class ParallelRenderTest(BlenderTest):
    def setUp(self):
        super(ParallelRenderTest, self).setUp()

        self.bpy.ops.scene.new(type='NEW')
        self.scn = self.bpy.context.scene
        self.scn.sequence_editor_create()
        self.scn.name = "TEST_SCENE"

        editing_screen = self.bpy.data.screens["Video Editing"]
        editing_screen.scene = self.scn

        try:
            shutil.rmtree('output')
        except OSError:
            pass
        os.makedirs('output')

    def tearDown(self):
        self.bpy.context.screen.scene = self.scn

    def _setup_video(self, project_prefs, user_prefs):
        render = self.scn.render
        render.resolution_x = 90
        render.resolution_y = 120
        render.resolution_percentage = 25
        render.pixel_aspect_x = 1
        render.pixel_aspect_y = 1
        render.fps = 24
        render.fps_base = 1

        render.image_settings.file_format = 'AVI_RAW'

        # Let us iterate over all properties and set them
        # Those are per user (visible under addon properties)
        pg = self.bpy.types.ParallelRenderPreferences
        addon_props = self.bpy.context.user_preferences.addons['parallel_render'].preferences
        for name in dir(pg):
            prop = getattr(pg, name)
            if isinstance(prop, tuple) and len(prop) == 2:
                setattr(addon_props, name, user_prefs[name])

        # Once we've set up everything let's recalculate
        # things that are not directly set by user.
        addon_props.update(self.bpy.context)

        # Those are per project (visible under properties tab widget)
        pg = self.bpy.types.ParallelRenderPropertyGroup
        panel = self.scn.parallel_render_panel
        for name in dir(pg):
            prop = getattr(pg, name)
            # This seems to filter out everything that is not a 
            # property we want to set.
            if isinstance(prop, tuple) and len(prop) == 2:
                setattr(panel, name, project_prefs[name])

        # Recalculate derived properties (ones not directly set
        # by user)
        panel.update(self.bpy.context)

    def _create_red_blue_green_sequence(self):
        color_strips = (
            ('red', (1, 0, 0)),
            ('green', (0, 1, 0)),
            ('blue', (0, 0, 1)),
        )
        for pos, (name, color) in enumerate(color_strips):
            end_pos = (pos + 1) * 10
            effect = self.scn.sequence_editor.sequences.new_effect(
                type='COLOR',
                channel=pos + 1,
                frame_start=1 + pos * 10,
                frame_end=end_pos,
                name='{} strip color'.format(name),
            )
            effect.color = color

        self.scn.frame_end = end_pos

    def _trigger_render(self):
        self.bpy.ops.render.parallel_render()

        while self.scn.parallel_render_panel.last_run_result == 'pending':
            LOGGER.info('waiting for output [state %s]', self.scn.parallel_render_panel.last_run_result)
            sleep(0.3)

    def _render_video(self, expected_state='done'):
        self.scn.render.filepath = '//output/test'
        self._trigger_render()
        self.assertEqual(self.scn.parallel_render_panel.last_run_result, expected_state)

    # Actual tests

    def test_parallel_render_panel(self):
        def reload_properties_panel():
            self.bpy.context.window.screen.areas[0].type = 'INFO'
            self.bpy.context.window.screen.areas[0].type = 'PROPERTIES'

        reload_properties_panel()

    def test_no_ffmpeg_fixed(self):
        for valid in (True, False):
            with self.subTest(ffmpeg_valid=valid):
                self._setup_video(
                    user_prefs={
                        'ffmpeg_executable': '',

                        # calculated, so shouldn' matter
                        'ffmpeg_status': '',
                        'ffmpeg_valid': False,
                    },
                    project_prefs={
                        'max_parallel': 8,
                        'overwrite': False,
                        'mixdown': True,
                        'concatenate': True,
                        'clean_up_parts': False,

                        'batch_type': 'fixed',
                        'fixed': 10,
                        
                        # unused here
                        'parts': 3,
                        'last_run_result': 'done',
                    },
                )
                self._create_red_blue_green_sequence()
                self._render_video()

                # Expect just the final render
                self.assertEqual(
                    sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                    ['test0001-0011.avi', 'test0001-0030.mp3', 'test0012-0022.avi', 'test0023-0030.avi']
                )

    def test_no_ffmpeg_parts(self):
        for valid in (True, False):
            with self.subTest(ffmpeg_valid=valid):
                self._setup_video(
                    user_prefs={
                        'ffmpeg_executable': '',

                        # calculated, so shouldn' matter
                        'ffmpeg_status': '',
                        'ffmpeg_valid': False,
                    },
                    project_prefs={
                        'max_parallel': 8,
                        'overwrite': False,
                        'mixdown': True,
                        'concatenate': True,
                        'clean_up_parts': False,

                        'batch_type': 'parts',
                        'parts': 4,
                        
                        # unused here
                        'fixed': 10,
                        'last_run_result': 'done',
                    },
                )
                self._create_red_blue_green_sequence()
                self._render_video()

                # Expect just the final render
                self.assertEqual(
                    sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                    ['test0001-0007.avi', 'test0001-0030.mp3', 'test0008-0015.avi', 'test0016-0022.avi','test0023-0030.avi']
                )

    def test_no_ffmpeg_no_mixdown(self):
        self._setup_video(
            user_prefs={
                'ffmpeg_executable': '',

                # calculated, so shouldn' matter
                'ffmpeg_status': '',
                'ffmpeg_valid': False,
            },
            project_prefs={
                'max_parallel': 8,
                'overwrite': False,
                'mixdown': False,
                'concatenate': True,
                'clean_up_parts': False,

                'batch_type': 'parts',
                'parts': 4,
                
                # unused here
                'fixed': 10,
                'last_run_result': 'done',
            },
        )
        self._create_red_blue_green_sequence()
        self._render_video()

        # Expect just the final render
        self.assertEqual(
            sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
            ['test0001-0007.avi', 'test0008-0015.avi', 'test0016-0022.avi','test0023-0030.avi']
        )

    def test_with_broken_ffmpeg(self):
        for ffmpeg_executable in (
            '/some/path/that/is/really/unlikely/to/exist',
            os.path.dirname(__file__), # pointing to directory is not valid
            __file__, # this is on assumption current file is not executable 
        ):
            with self.subTest(ffmpeg_executable=ffmpeg_executable):
                self._setup_video(
                    user_prefs={
                        'ffmpeg_executable': ffmpeg_executable,

                        # calculated, so shouldn' matter
                        'ffmpeg_status': '',
                        'ffmpeg_valid': False,
                    },
                    project_prefs={
                        'max_parallel': 8,
                        'overwrite': False,
                        'mixdown': True,
                        'concatenate': True,
                        'clean_up_parts': False,

                        'batch_type': 'fixed',
                        'fixed': 10,
                        
                        # unused here
                        'parts': 3,
                        'last_run_result': 'done',
                    },
                )

                self._create_red_blue_green_sequence()
                self._render_video()

                # Expect just the final render
                self.assertEqual(
                    sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                    ['test0001-0011.avi', 'test0001-0030.mp3', 'test0012-0022.avi', 'test0023-0030.avi']
                )

    def test_with_ffmpeg_no_cleanup(self):
        self._setup_video(
            user_prefs={
                'ffmpeg_executable': self.FFMPEG_EXECUTABLE,

                # calculated, so shouldn' matter
                'ffmpeg_status': '',
                'ffmpeg_valid': False,
            },
            project_prefs={
                'max_parallel': 8,
                'overwrite': False,
                'mixdown': True,
                'concatenate': True,
                'clean_up_parts': False,

                'batch_type': 'fixed',
                'fixed': 10,
                
                # unused here
                'parts': 3,
                'last_run_result': 'done',
            },
        )

        self._create_red_blue_green_sequence()
        self._render_video()

        self.assertTrue(self.bpy.context.user_preferences.addons['parallel_render'].preferences.ffmpeg_valid)

        # Expect just the final render and all parts
        self.assertEqual(
            sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
            ['test0001-0011.avi', 'test0001-0030.avi', 'test0001-0030.mp3', 'test0012-0022.avi', 'test0023-0030.avi']
        )

    def test_with_ffmpeg_with_cleanup_save(self):
        self._setup_video(
            user_prefs={
                'ffmpeg_executable': self.FFMPEG_EXECUTABLE,

                # calculated, so shouldn' matter
                'ffmpeg_status': '',
                'ffmpeg_valid': False,
            },
            project_prefs={
                'max_parallel': 8,
                'overwrite': False,
                'mixdown': True,
                'concatenate': True,
                'clean_up_parts': True,

                'batch_type': 'fixed',
                'fixed': 10,
                
                # unused here
                'parts': 3,
                'last_run_result': 'done',
            },
        )

        self._create_red_blue_green_sequence()
        self.scn.render.filepath = '//output/test'
        filepath = os.path.join(os.path.abspath('.'), 'test.blend')

        self.assertEqual(
            self.bpy.ops.wm.save_mainfile(filepath=filepath),
            {'FINISHED'},
        )

        self.assertTrue(self.bpy.data.is_saved)
        self.assertTrue(os.path.exists(self.bpy.data.filepath))

        # FIXME: sadly even though I just called `save_mainfile` we
        # still get back "is_dirty"
        # I shouldn't need to mock it, it should just work and this:
        # self.assertFalse(self.bpy.data.is_dirty)
        # should be True
        with mock.patch('parallel_render._need_temporary_file') as needs_temporary:
            needs_temporary.return_value = False

            self._trigger_render()

            self.assertTrue(self.bpy.data.is_saved)
            # self.assertFalse(self.bpy.data.is_dirty)

            # Expect just the final render
            self.assertEqual(
                sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                ['test0001-0030.avi']
            )

    def test_with_child_failure(self):
        self._setup_video(
            user_prefs={
                'ffmpeg_executable': self.FFMPEG_EXECUTABLE,

                # calculated, so shouldn' matter
                'ffmpeg_status': '',
                'ffmpeg_valid': False,
            },
            project_prefs={
                'max_parallel': 8,
                'overwrite': False,
                'mixdown': True,
                'concatenate': True,
                'clean_up_parts': True,

                'batch_type': 'fixed',
                'fixed': 8,
                
                # unused here
                'parts': 4,
                'last_run_result': 'done',
            },
        )

        self._create_red_blue_green_sequence()

        with mock.patch('subprocess.Popen') as Popen:
            Popen.side_effect = Exception('TEST')
            self._render_video(expected_state='failed')
            # Expect nothing, as we can't Popen
            self.assertEqual(
                sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                []
            )

        #with mock.patch('parallel_render.MessageChannel') as MessageChannel:
        #    MessageChannel.return_value = Exception('TEST')
        #    self._render_video(expected_state='failed')
        #    self.assertTrue(MessageChannel.called)

        #    # Expect nothing, as we can't Popen
        #    self.assertEqual(
        #        sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
        #        []
        #    )

        base_dir = os.path.realpath('output')

        def create_output(filepath, rc):
            process_mock = mock.MagicMock()
            if filepath is not None:
                filepath = os.path.join(base_dir, filepath)
                LOGGER.info('Creating dummy file %s', filepath)
                with open(filepath, 'w'):
                    pass
            process_mock.returncode = int(rc)
            process_mock.wait.return_value = int(rc)
            return process_mock

        processes = iter((
            create_output(filepath='test0001-0009.avi', rc=0),
            create_output(filepath=None, rc=-11),
            create_output(filepath='test0019-0027.avi', rc=1),
            create_output(filepath=None, rc=-12),
        ))

        with mock.patch('parallel_render.Pool') as Pool:
            Pool().__enter__().imap_unordered = map
            Pool().__enter__().map = map
            with mock.patch('subprocess.Popen') as Popen:
                Popen.side_effect = lambda *_, **_kw: next(processes)
                with mock.patch('parallel_render.MessageChannel') as MessageChannel:
                    MessageChannel().recv.side_effect = [
                        {'output_file': os.path.join(base_dir, 'test0001-0009.avi'), 'current_frame': 11},
                        None,

                        {'output_file': os.path.join(base_dir, 'test0010-0018.avi'), 'current_frame': 12},
                        None,

                        {'output_file': os.path.join(base_dir, 'test0019-0027.avi'), 'current_frame': 25},
                        None,

                        None,
                    ]
                    with mock.patch('socket.socket') as socket:
                        socket().getsockname.return_value = 'does not matter'
                        socket().accept.return_value = (mock.MagicMock(), mock.MagicMock())
                        self._render_video(expected_state='failed')

                        # Expect nothing, as we can't Popen
                        self.assertEqual(
                            sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
                            ['test0001-0009.avi']
                        )

def run_tests(args):
    extra_pythonpath = args[1]
    ffmpeg_path = args[2]
    sys.path.append(extra_pythonpath)
    LOGGER.info("Appending extra PYTHONPATH %s", extra_pythonpath)

    import coverage
    coverage.process_startup()

    BlenderTest.FFMPEG_EXECUTABLE = ffmpeg_path
    unittest.main(
        argv=['<blender executable>'] + args[3:],
    )

def launch_tests_under_blender(args):
    import coverage
    blender_executable = args.pop(1)
    ffmpeg_executable = args.pop(1)
    coverage_module_path = os.path.realpath(os.path.dirname(os.path.dirname(coverage.__file__)))
    cmd = (
        blender_executable,
        '--background',
        '-noaudio',
        '--factory-startup',
        '--python', os.path.abspath(__file__),
        '--',
        'run',
        coverage_module_path,
        os.path.realpath(ffmpeg_executable)
    ) + tuple(args[1:])

    LOGGER.info('Running: %s', cmd)

    env = dict(os.environ)
    env['BLENDER_USER_SCRIPTS'] = os.path.realpath('scripts')
    env['PYTHONPATH'] = coverage_module_path
    outdir = os.path.realpath('tests_output')
    subprocess.check_call(cmd, cwd=outdir, env=env)

MAIN_ACTIONS = {
    'test': launch_tests_under_blender,
    'run': run_tests,
}

def main():
    logging.basicConfig(level=logging.INFO)
    try:
        args = sys.argv[sys.argv.index('--') + 1:]
    except ValueError:
        args = sys.argv[1:]

    MAIN_ACTIONS[args[0]](args)

if __name__ == "__main__":
    main()

