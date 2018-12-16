"""
Entry point for tests.
To run:

PYTHONPATH=tests python3.6 tests/parallel_render.py test <path to blender>

"""
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

    def tearDown(self):
        self.bpy.context.screen.scene = self.scn

    def setup_video_out(self):
        render = self.scn.render
        render.resolution_x = 1280
        render.resolution_y = 720
        render.resolution_percentage = 25
        render.pixel_aspect_x = 1
        render.pixel_aspect_y = 1
        render.fps = 24
        render.fps_base = 1

        render.image_settings.file_format = 'AVI_RAW'
        self.scn.parallel_render_panel.batch_type = 'fixed'
        self.scn.parallel_render_panel.fixed = 10
        self.scn.parallel_render_panel.concatenate = True
        self.scn.parallel_render_panel.clean_up_parts = True

        addon_props = self.bpy.context.user_preferences.addons['parallel_render'].preferences
        addon_props.update(self.bpy.context)

    def test_parallel_render_panel(self):
        def reload_properties_panel():
            self.bpy.context.window.screen.areas[0].type = 'INFO'
            self.bpy.context.window.screen.areas[0].type = 'PROPERTIES'

        reload_properties_panel()

    def test_first(self):
        LOGGER.info('test one')

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

        self.setup_video_out()
        self.scn.render.filepath = '//output/test'
        self.bpy.ops.wm.save_as_mainfile(filepath='test.blend')
        what = self.bpy.ops.render.parallel_render()

        while self.scn.parallel_render_panel.last_run_result == 'pending':
            LOGGER.info('waiting for output [state %s]', self.scn.parallel_render_panel.last_run_result)
            sleep(0.3)

        self.assertEqual(self.scn.parallel_render_panel.last_run_result, 'done')
        # Expect just the final render
        self.assertEqual(
            sorted(fname for fname in os.listdir('output/') if fname[0] != '.'),
            ['test0001-0011.avi', 'test0001-0030.mp3', 'test0012-0022.avi', 'test0023-0030.avi']
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

    unittest.main(
        argv=['<blender executable>'] + args[2:],
        exit=False
    )

def make_tests_coveragerc(base_file, test_outdir):
    tests_coverage_rc = os.path.realpath(os.path.join(test_outdir, 'coverage.tests.rc'))
    with open(tests_coverage_rc, 'w') as out:
        with open(base_file, 'r') as src:
            shutil.copyfileobj(src, out)
        out.write('data_file = {}\n'.format(os.path.join(test_outdir, '.coverage')))
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
    cmd = (
        blender_executable,
        '--background',
        '-noaudio',
        '--factory-startup',
        '--python', os.path.abspath(__file__),
        '--',
        'run',
        os.path.realpath(os.path.dirname(os.path.dirname(coverage.__file__))),
    )

    LOGGER.info('Running: %s', cmd)

    env = dict(os.environ)
    env['BLENDER_USER_SCRIPTS'] = os.path.realpath('scripts')
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

