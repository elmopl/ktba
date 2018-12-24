"""
Entry point for tests.
To run:

PYTHONPATH=tests python3.6 tests/parallel_render.py test <path to blender> <path to ffmpeg executable>

"""
from itertools import product
from time import sleep
import logging
import os
import shutil
import subprocess
import sys
import unittest

BLENDER_EXECUTABLE = None
LOGGER = logging.getLogger('tests_runtime')

class BlenderTest(unittest.TestCase):
    FFMPEG_EXECUTABLE = None

    @classmethod
    def setUpClass(cls):
        import bpy
        cls.bpy = bpy

    def setUp(self):
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

    def tearDown(self):
        self.bpy.context.screen.scene = self.scn

    def _setup_video(self, project_prefs, user_prefs):
        render = self.scn.render
        render.resolution_x = 1280
        render.resolution_y = 720
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

    def _render_video(self):
        self.scn.render.filepath = '//output/test'
        self.bpy.ops.wm.save_as_mainfile(filepath='test.blend')
        what = self.bpy.ops.render.parallel_render()

        while self.scn.parallel_render_panel.last_run_result == 'pending':
            LOGGER.info('waiting for output [state %s]', self.scn.parallel_render_panel.last_run_result)
            sleep(0.3)

        self.assertEqual(self.scn.parallel_render_panel.last_run_result, 'done')

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

    def test_with_ffmpeg_with_cleanup(self):
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
        self._render_video()

        # Expect just the final render
        self.assertEqual(
            sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
            ['test0001-0030.avi']
        )




def start_coverage():
    try:
        LOGGER.info("Preparing coverage for %s", sys.argv)
        import coverage
        coverage.process_startup()
        LOGGER.info("Started coverage")
    except ImportError as exc:
        LOGGER.warning("Could not import coverage module", exc_info=True)

def run_tests(args):
    extra_pythonpath = args[1]
    ffmpeg_path = args[2]
    sys.path.append(extra_pythonpath)
    LOGGER.info("Appending extra PYTHONPATH %s", extra_pythonpath)
    start_coverage()

    # Now that we have coverage enabled reload modules
    # to go through load/unload functions
    import bpy
    bpy.ops.wm.addon_enable(module='parallel_render')
    bpy.ops.script.reload() 
    LOGGER.info('bpy.utls.script_paths: %s', bpy.utils.script_paths())
    LOGGER.info('cwd: %s', os.getcwd())

    BlenderTest.FFMPEG_EXECUTABLE = ffmpeg_path
    unittest.main(
        argv=['<blender executable>'] + args[3:],
        exit=False
    )

def make_tests_coveragerc(base_file, test_outdir):
    tests_coverage_rc = os.path.realpath(os.path.join(test_outdir, 'coverage.tests.rc'))
    with open(tests_coverage_rc, 'w') as out:
        with open(base_file, 'r') as src:
            shutil.copyfileobj(src, out)
        out.write('data_file = {}\n'.format(os.path.join(test_outdir, '.coverage')))
        out.write('omit = \n')
        out.write('    */scripts/startup/*\n')
        out.write('    */scripts/modules/*\n')
        out.write('    */scripts/addons/cycles/*\n')
        out.write('    */scripts/addons/io_*/*\n')
        out.write('\n')
        out.write('[paths]\n')
        out.write('source = \n')
        out.write('  */scripts\n')
    os.environ['COVERAGE_PROCESS_START'] = tests_coverage_rc

def launch_tests_under_blender(args):
    outdir = os.path.realpath('tests_output')
    shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)

    make_tests_coveragerc(
        base_file=os.path.join(os.path.dirname(__file__), 'coverage.rc'),
        test_outdir=outdir
    )

    start_coverage()

    import coverage
    blender_executable = args.pop(1)
    ffmpeg_executable = args.pop(1)
    cmd = (
        blender_executable,
        '--background',
        '-noaudio',
        '--factory-startup',
        '--python', os.path.abspath(__file__),
        '--',
        'run',
        os.path.realpath(os.path.dirname(os.path.dirname(coverage.__file__))),
        os.path.realpath(ffmpeg_executable)
    ) + tuple(args[1:])

    LOGGER.info('Running: %s', cmd)

    env = dict(os.environ)
    env['BLENDER_USER_SCRIPTS'] = os.path.realpath('scripts')
    subprocess.check_call(cmd, cwd=outdir, env=env)

    cov = coverage.Coverage(config_file=os.environ['COVERAGE_PROCESS_START'])
    cov.combine()
    cov.report(show_missing=True)

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

