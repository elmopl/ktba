from .parametrised import ParametrisedValue as PV
from .parametrised import ParametrisedMatrix as Matrix
from math import radians

panel_spacing = (PV('width') - (PV('frame_width') + PV('panel_offset_side')) * 2 - PV('instance_count') * PV('panel_width')) / (PV('instance_count') - .99)
panel_left_base = PV('frame_width') + PV('panel_offset_side')
panel_left_side = panel_left_base + PV('instance') * (PV('panel_width') + panel_spacing)

DESCRIPTION = {
    'parameters': {
        'lengths': {
            'height': {
                'default': 2.140,
                'base_transform': Matrix.Identity(4),
            },
            'width': {
                'default': 0.9,
                'base_transform': Matrix.Rotation(radians(90), 4, 'Y'),
            },
            'depth': {
                'default': 0.044,
                'base_transform': Matrix.Rotation(radians(-90), 4, 'X'),
            },
            'frame_width': {
                'default': 0.1,
                'base_transform': Matrix.Translation(z=PV('height') / 2)
                                @ Matrix.Rotation(radians(90), 4, 'Y'),
            },
            'sill_height': {
                'default': 0.1,
                'base_transform': Matrix.Translation(x=PV('width') / 2),
            },
            'panel_height': {
                'default': 0.9,
                'base_transform': Matrix.Translation(
                                    x=PV('panel_width') / 2
                                     +PV('panel_offset_side') 
                                     +PV('frame_width'),
                                    z=PV('sill_height') + PV('panel_offset_bottom'),
                                  )
            },
            'panel_width': {
                'default': 0.15,
                'update': lambda l, c: (l['width'] - 2 * (l['panel_offset_side'] + l['frame_width'])) / (c['panels'] or 1) / 2,
                'base_transform': Matrix.Translation(
                                    z=PV('panel_height') / 2
                                     +PV('sill_height'),
                                    x=panel_left_base
                                  )
                                  @ Matrix.Rotation(radians(90), 4, 'Y'),
            },
            'panel_offset_bottom': {
                'default': 0.104,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width') + PV('panel_offset_side') + PV('panel_width') / 2,
                                    z=PV('sill_height')
                                  )
            },
            'panel_offset_side': {
                'default': 0.104,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width'),
                                    z=PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height') / 2
                                  )
                                @ Matrix.Rotation(radians(90), 4, 'Y')
            },
        },
        'counts': {
            'panels': {
                'type': 'count',
                'default': 3,
            },
        }
    },
    'geometries': [
        {
            'name': 'guide_planes',
            'vertices': (
                (0, 0, 0),
                ('width', 0, 0),
                ('width', 'depth', 0),
                (0, 'depth', 0),

                (0, 0, 'height'),
                ('width', 0, 'height'),
                ('width', 'depth', 'height'),
                (0, 'depth', 'height'),
            ),
            'faces': (
                (0, 1, 2, 3),
                (4, 5, 6, 7),
            ),
        },
        {
            'name': 'frame_left',
            'vertices': (
                (0,             0,       'sill_height'),
                ('frame_width', 0,       'sill_height'),
                ('frame_width', 'depth', 'sill_height'),
                (0,             'depth', 'sill_height'),

                (0,             0,       PV('height') - PV('frame_width')),
                ('frame_width', 0,       PV('height') - PV('frame_width')),
                ('frame_width', 'depth', PV('height') - PV('frame_width')),
                (0,             'depth', PV('height') - PV('frame_width')),
            ),
            'faces': (
                (0, 1, 2, 3),
                (4, 5, 6, 7),
                (0, 1, 5, 4),
                (1, 2, 6, 5),
                (0, 3, 7, 4),
            ),
        },
        {
            'name': 'frame_right',
            'vertices': (
                (PV('width') - PV('frame_width'),  0,       'sill_height'),
                (PV('width'),                      0,       'sill_height'),
                (PV('width'),                      'depth', 'sill_height'),
                (PV('width') - PV('frame_width'),  'depth', 'sill_height'),

                (PV('width') - PV('frame_width'),  0,       PV('height') - PV('frame_width')),
                (PV('width'),                      0,       PV('height') - PV('frame_width')),
                (PV('width'),                      'depth', PV('height') - PV('frame_width')),
                (PV('width') - PV('frame_width'),  'depth', PV('height') - PV('frame_width')),
            ),
            'faces': (
                (0, 1, 2, 3),
                (4, 5, 6, 7),
                (0, 1, 5, 4),
                (1, 2, 6, 5),
                (0, 3, 7, 4),
            ),
        },
        {
            'name': 'frame_top',
            'vertices': (
                (0,            0,       PV('height') - PV('frame_width')),
                (PV('width'),  0,       PV('height') - PV('frame_width')),
                (PV('width'),  'depth', PV('height') - PV('frame_width')),
                (0,            'depth', PV('height') - PV('frame_width')),

                (0,            0,       PV('height')),
                (PV('width'),  0,       PV('height')),
                (PV('width'),  'depth', PV('height')),
                (0,            'depth', PV('height')),
            ),
            'faces': (
                (0, 1, 2, 3),
                (4, 5, 6, 7),
                (0, 1, 5, 4),
                (1, 2, 6, 5),
                (0, 3, 7, 4),
            ),
        },
        {
            'name': 'panel',
            'instances': 'panels',
            'vertices': (
                (panel_left_side,                       0, PV('sill_height') + PV('panel_offset_bottom')),
                (panel_left_side + PV('panel_width'),   0, PV('sill_height') + PV('panel_offset_bottom')),
                (panel_left_side + PV('panel_width'),   0, PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height')),
                (panel_left_side,                       0, PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height')),
            ),
            'faces': (
                (0, 1, 2, 3),
            ),
        }
    ]
}
