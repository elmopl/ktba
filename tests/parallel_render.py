from time import sleep
import logging
import os
import shutil
import subprocess
import sys
import unittest

BLENDER_EXECUTABLE = None

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

    def test_first(self):
        logging.info('test one')

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
            print('waiting for output')
            sleep(0.1)

        self.assertEqual(self.scn.parallel_render_panel.last_run_result, 'done')
        self.assertEqual(
            [fname for fname in os.listdir('output/') if fname[0] != '.'],
            [
                'test{:04d}-{:04d}.avi'.format(self.scn.frame_start, self.scn.frame_end),
            ]
        )


def launch_tests_under_blender(args):
    blender_executable = args.pop(1)
    cmd = (
        blender_executable,
        '--background',
        '--python', os.path.abspath(__file__),
        '--',
        'run',
    )

    logging.info('Running: %s', cmd)

    outdir = 'tests_output'
    shutil.rmtree(outdir)
    os.makedirs(outdir, exist_ok=True)
    subprocess.check_call(cmd, cwd=outdir)

def run_tests(args):
    unittest.main(argv=['<blender executable>'] + args[1:])

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

