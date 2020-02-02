from .parametrised import ParametrisedMatrix as Matrix
from .parametrised import ParametrisedValue as PV
from .parametrised import rectangle
from itertools import chain
from math import radians

panel_spacing = (PV('width') - (PV('frame_width') + PV('panel_offset_side')) * 2 - PV('instance_count') * PV('panel_width')) / (PV('instance_count') - .99)
panel_left_base = PV('frame_width') + PV('panel_offset_side')
panel_left_side = panel_left_base + PV('instance') * (PV('panel_width') + panel_spacing)
body_y = (PV('frame_depth') - PV('depth')) / 2

def body_faces(furnigen, instance):
    panel_count = furnigen.counts['panels'].value
    last = panel_count - 1
    faces = [
        (3, 0, ('panel-0', 4), ('panel-0', 7)),
        (1, 2, (f'panel-{last}', 6), (f'panel-{last}', 5)),
        (4, 5, 6, 7), # back face
        (4, 5, 1, 0), # bottom
        (1, 5, 6, 2), # right
        (3, 2, 6, 7), # top
        (3, 7, 4, 0), # left
    ]

    def _join_panel_to_frame(frame_left, frame_right, panel_left, panel_right):
        bottom_vertices = tuple(chain(*[
            (
                (f'panel-{num}', panel_left),
                (f'panel-{num}', panel_right),
            )
            for num in range(panel_count)
        ]))
        pairs = tuple(zip(bottom_vertices, bottom_vertices[1:]))
        midpoint = len(pairs)//2
        faces.extend(
            (frame_left, vert1, vert2)
            for vert1, vert2 in pairs[:midpoint]
        )
        faces.extend(
            (frame_right, vert1, vert2)
            for vert1, vert2 in pairs[midpoint+1:]
        )

        faces.append(
            (frame_right, frame_left) + pairs[midpoint]
        )

    _join_panel_to_frame(0, 1, 4, 5)
    _join_panel_to_frame(3, 2, 7, 6)

    for face in faces:
        print('>>>', face)

    return faces

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
                'base_transform': Matrix.Translation(y=body_y, z='sill_height', x='frame_width')
                                @ Matrix.Rotation(radians(90), 4, 'X'),
            },
            'frame_width': {
                'default': 0.1,
                'base_transform': Matrix.Translation(z=PV('height') / 2)
                                @ Matrix.Rotation(radians(90), 4, 'Y'),
            },
            'frame_depth': {
                'default': 0.11,
                'base_transform': Matrix.Translation(z=PV('height') / 1.5)
                                @ Matrix.Rotation(radians(-90), 4, 'X'),
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
                'default': 0.14,
                'update': lambda l, c: (l['width'] - 2 * (l['panel_offset_side'] + l['frame_width'])) / (c['panels'] or 1) / 2,
                'base_transform': Matrix.Translation(
                                    z=PV('panel_height') / 2
                                     +PV('sill_height'),
                                    x=panel_left_base
                                  )
                                  @ Matrix.Rotation(radians(90), 4, 'Y'),
            },
            'panel_offset_bottom': {
                'default': 0.1,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width') + PV('panel_offset_side') + PV('panel_width') / 2,
                                    z=PV('sill_height')
                                  )
            },
            'panel_offset_side': {
                'default': 0.1,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width'),
                                    z=PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height') / 2
                                  )
                                @ Matrix.Rotation(radians(90), 4, 'Y')
            },

            'panel_bevel_width': {
                'default': 0.022,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width') + PV('panel_offset_side'),
                                    z=PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height') / 3
                                  )
                                @ Matrix.Rotation(radians(90), 4, 'Y')
            },

            'panel_bevel_depth': {
                'default': 0.014,
                'base_transform': Matrix.Translation(
                                    x=PV('frame_width') + PV('panel_offset_side'),
                                    z=PV('sill_height') + PV('panel_offset_bottom') + PV('panel_height') / 3
                                  )
                                @ Matrix.Rotation(radians(-90), 4, 'X'),
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
                ('width', 'frame_depth', 0),
                (0, 'frame_depth', 0),

                (0, 0, 'height'),
                ('width', 0, 'height'),
                ('width', 'frame_depth', 'height'),
                (0, 'frame_depth', 'height'),
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
                ('frame_width', 'frame_depth', 'sill_height'),
                (0,             'frame_depth', 'sill_height'),

                (0,             0,             PV('height') - PV('frame_width')),
                ('frame_width', 0,             PV('height') - PV('frame_width')),
                ('frame_width', 'frame_depth', PV('height') - PV('frame_width')),
                (0,             'frame_depth', PV('height') - PV('frame_width')),
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
                (PV('width') - PV('frame_width'),  0,             'sill_height'),
                (PV('width'),                      0,             'sill_height'),
                (PV('width'),                      'frame_depth', 'sill_height'),
                (PV('width') - PV('frame_width'),  'frame_depth', 'sill_height'),

                (PV('width') - PV('frame_width'),  0,             PV('height') - PV('frame_width')),
                (PV('width'),                      0,             PV('height') - PV('frame_width')),
                (PV('width'),                      'frame_depth', PV('height') - PV('frame_width')),
                (PV('width') - PV('frame_width'),  'frame_depth', PV('height') - PV('frame_width')),
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
                (PV('width'),  'frame_depth', PV('height') - PV('frame_width')),
                (0,            'frame_depth', PV('height') - PV('frame_width')),

                (0,            0,       PV('height')),
                (PV('width'),  0,       PV('height')),
                (PV('width'),  'frame_depth', PV('height')),
                (0,            'frame_depth', PV('height')),
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
                (
                    Matrix.Translation(
                        x=panel_left_side + PV('panel_bevel_width'),
                        y=body_y + PV('panel_bevel_depth'),
                        z=PV('sill_height') + PV('panel_offset_bottom') + PV('panel_bevel_width')
                    )
                    @ rectangle(PV('panel_width') - PV('panel_bevel_width') * 2, PV('panel_height') - PV('panel_bevel_width') * 2).T
                ).T.rows
                +
                (
                    Matrix.Translation(x=panel_left_side, y=body_y, z=PV('sill_height') + PV('panel_offset_bottom'))
                    @ rectangle('panel_width', 'panel_height').T
                ).T.rows
            ),
            'faces': (
                (0, 1, 2, 3),

                (4, 5, 1, 0),
                (1, 5, 6, 2),
                (6, 2, 3, 7),
                (3, 7, 4, 0),

                (
                    ('previous', 5),
                    4,
                    7,
                    ('previous', 6),
                ),
            ),
        },
        {
            'name': 'body',
            'vertices': (
                (
                    Matrix.Translation(
                        x='frame_width',
                        y=body_y,
                        z='sill_height',
                    )
                    @ rectangle(PV('width') - PV('frame_width') * 2, PV('height') - PV('frame_width') - PV('sill_height')).T
                ).T.rows
                + 
                (
                    Matrix.Translation(
                        x='frame_width',
                        y=body_y + PV('depth'),
                        z='sill_height',
                    )
                    @ rectangle(PV('width') - PV('frame_width') * 2, PV('height') - PV('frame_width') - PV('sill_height')).T
                ).T.rows
            ),
            'faces': body_faces,
        },

    ]
}

