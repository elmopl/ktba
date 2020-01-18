from mathutils import Matrix
from mathutils import Vector

class ParametrisedValue(object):
    def __init__(self, expr, parameters=None):
        if isinstance(expr, ParametrisedValue):
            self.expr = expr.expr
            self.parameters = set(expr.parameters)
        else:
            self.expr = expr
            self.parameters = parameters

            if self.parameters is None:
                self.parameters = set()
                if isinstance(expr, str):
                    self.parameters.add(expr)
                else:
                    self.expr = float(expr)

    @property
    def constant(self):
        return not self.parameters

    def __repr__(self):
        return str(self.expr)

    def _apply_op(self, other, op, name):
        if not isinstance(other, ParametrisedValue):
            other = ParametrisedValue(other)

        if self.constant and other.constant:
            res = getattr(self.expr, name)(other.expr)
            parameters = None
        else:
            parameters = self.parameters | other.parameters
            res = f'({self}) {op} ({other})'
        return ParametrisedValue(res, parameters)

    def __mul__(self, other):
        return self._apply_op(other, '*', '__mul__')

    def __add__(self, other):
        return self._apply_op(other, '+', '__add__')

    def __sub__(self, other):
        return self._apply_op(other, '-', '__sub__')

    def __truediv__(self, other):
        return self._apply_op(other, '/', '__truediv__')
    
    def subst(self, **values):
        new_params = set(self.parameters)
        new_expr = self.expr
        for name, value in values.items():
            if name in new_params:
                new_params.remove(name)
                new_expr = new_expr.replace(f'({name})', f'{value}')
        return ParametrisedValue(new_expr, new_params)

    def calculate(self, parameters):
        if self.constant:
            return self.expr
        else:
            return eval(self.expr, parameters)

class ParametrisedMatrix(object):
    @staticmethod
    def Translation(x=0, y=0, z=0):
        return ParametrisedMatrix([
            [1, 0, 0, x],
            [0, 1, 0, y],
            [0, 0, 1, z],
            [0, 0, 0, 1],
        ])

    @staticmethod
    def Rotation(*a, **kw):
        return ParametrisedMatrix(Matrix.Rotation(*a, **kw))

    @staticmethod
    def Identity(*a, **kw):
        return ParametrisedMatrix(Matrix.Identity(*a, **kw))

    def __init__(self, matrix):
        self.matrix = tuple(
            tuple(map(ParametrisedValue, row))
            for row in matrix
        )

    def __matmul__(self, other):
        a = self.matrix
        b = tuple(zip(*other.matrix))
        return ParametrisedMatrix(
            (
                sum(
                    (
                        ParametrisedValue(ele_a * ele_b)
                        for ele_a, ele_b in zip(row_a, col_b)
                    ),
                    ParametrisedValue(0)
                ) 
                for col_b in b
            )
            for row_a in a
        )

    def __repr__(self):
        return str(tuple(tuple(row) for row in self.matrix))

    def calculate(self, parameters):
        return Matrix(tuple(
            Vector(cell.calculate(parameters) for cell in row)
            for row in self.matrix
        ))

