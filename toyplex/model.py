import numpy as np
from toyplex.components import Var, LinExpr, LinConstr
from toyplex.simplex import Simplex
import math
import copy
__version__ = '0'


class Node:
    """Primal simplex method that solves a linear program expressed in standard form.

    It starts with a feasible basic solution, and moves from one feasible basic solution to
    another to decrease objective function, until reaching the minimum.
    """
    def __init__(self, key):
        """Initiates a Simplex object."""
        self.key = key
        # code -1: solving, 0: solved, 1: unbounded, 2: infeasible
        self.code = -1

        # default minimization
        self.sense = 'min'

        # decision vars, union of conts, bins and ints
        self.vars = {}
        self.conts = {}
        self.bins = {}
        self.ints = {}
        # non-decision vars
        self.slacks = {}
        self.surplus = {}
        # constraints
        self.constrs = []
        self.n_vars = 0
        self.n_constrs = 0
        # objective expression, objective array
        self.objval = math.inf
        self.objexpr = None
        self.objective = None
        # tab
        self.tab = None
        self.spx = None

    def add_var(self, type='cont', lb=0, ub=math.inf, name=None):
        """Adds a decision variable."""
        if type == 'cont':
            if name is None:
                name = 'x' + str(int(len(self.conts))+1)
            self.conts[name] = Var(name, type=type)
            self.vars.update(self.conts)
            if lb > 0:
                self.add_constr(self.conts[name] >= lb)
            if ub is not math.inf:
                self.add_constr(self.conts[name] <= ub)
        elif type == 'bin':
            if name is None:
                name = 'b' + str(int(len(self.bins))+1)
            self.bins[name] = Var(name, type=type)
            self.vars.update(self.bins)
            self.add_constr(self.bins[name] <= 1)
        elif type == 'int':
            if name is None:
                name = 'i' + str(int(len(self.ints))+1)
            self.ints[name] = Var(name, type=type)
            self.vars.update(self.ints)
        return self.vars[name]

    def add_constr(self, constr: LinConstr):
        """Adds a linear constraint, and add slack and surplus variables as needed."""
        # beautiful
        if constr.sense == '==':
            pass
        # slack variable
        elif constr.sense == '<=':
            name = 's' + str(int(len(self.slacks))+1)
            self.slacks[name] = Var(name, type='cont')
            constr.coeffs[name] = 1
        # surplus variable
        elif constr.sense == '>=':
            name = 'p' + str(int(len(self.surplus)) + 1)
            self.surplus[name] = Var(name, type='cont')
            constr.coeffs[name] = -1
        self.constrs.append(constr)

    def set_tab(self):
        """Sets tab."""
        self.tab = None
        var_col = {}
        for idx, key in enumerate([*self.vars.keys()]+[*self.slacks.keys()]+[*self.surplus.keys()]):
            var_col[key] = idx
        self.n_constrs = len(self.constrs)
        self.n_vars = len(self.vars) + len(self.slacks) + len(self.surplus)
        self.tab = np.zeros((self.n_constrs, self.n_vars + 1))
        for idx, constr in enumerate(self.constrs):
            for key in constr.coeffs.keys():
                if constr.coeffs[key] != 0:
                    self.tab[idx][var_col[key]] = constr.coeffs[key]
                self.tab[idx][-1] = constr.b
        self.tab = np.vstack((self.tab, self.objective))

    def set_objective(self, objexpr: LinExpr, sense='min'):
        """Sets objective."""
        self.objexpr = objexpr
        self.objective = np.zeros(len(self.vars) + len(self.slacks) + len(self.surplus) + 1)

        if 'const' in objexpr.coeffs.keys():
            self.objective[-1] = -objexpr.coeffs['const']
            del objexpr.coeffs['const']
        else:
            self.objective[-1] = 0

        var_col = {}
        for idx, key in enumerate(self.vars.keys()):
            var_col[key] = idx
        for key in objexpr.coeffs.keys():
            if objexpr.coeffs[key] != 0:
                self.objective[var_col[key]] = objexpr.coeffs[key]

        if sense == 'max':
            self.sense = sense
            self.objective = -self.objective

    def describe(self):
        """Describes the linear program."""
        print('{}\t{}'.format(self.sense, self.objexpr))
        for idx, constr in enumerate(self.constrs):
            if idx == 0:
                print('st\t{}'.format(constr))
            else:
                print('\t{}'.format(constr))

    def optimize(self, verbose=False):
        """Solves linear program."""
        self.set_tab()

        # simplex algorithm
        names = [name for name in self.vars] + [name for name in self.slacks] + [name for name in self.surplus]
        self.spx = Simplex(self.tab, names=names)
        self.spx.solve(verbose=verbose)
        self.code = self.spx.code

        # result
        if self.code == 0:
            if self.sense == 'min':
                self.objval = -self.spx.tab[-1][-1]
            elif self.sense == 'max':
                self.objval = self.spx.tab[-1][-1]
            for idx, key in enumerate(self.vars.keys()):
                self.vars[key].val = 0
                if len(np.where(self.spx.tab[:-1, idx] > 0)[0]) == 1:
                    arr = np.where(self.spx.tab[:, idx] == 1)[0]
                    if len(arr) == 1:
                        self.vars[key].val = self.spx.tab[:, -1][arr[0]]


class Model:
    """A mixed integer programming model.
    """
    def __init__(self):
        """Initiates a MIP model."""
        # code -1: solving, 0: solved, 1: unbounded, 2: infeasible
        self.code = -1

        # tree
        root = Node(0)
        self.nodes = {root.key: root}
        self.candidates = {root.key: root}
        self.icmbkey = None
        self.icmbval = math.inf

        # default minimization
        self.sense = 'min'

        # decision vars, union of conts, bins and ints
        self.vars = {}
        self.conts = {}
        self.bins = {}
        self.ints = {}
        # non-decision vars
        self.slacks = {}
        self.surplus = {}
        # constraints
        self.constrs = []
        self.n_vars = 0
        self.n_constrs = 0
        # objective expression, objective array
        self.objkey = 0
        self.objval = math.inf
        self.objexpr = None
        self.objective = None

    def add_var(self, type='cont', lb=None, ub=None, name=None):
        """Adds a decision variable."""
        if lb is None and ub is None:
            self.nodes[0].add_var(type=type, name=name)
        elif lb is None and ub is not None:
            self.nodes[0].add_var(type=type, ub=ub, name=name)
        elif lb is not None and ub is None:
            self.nodes[0].add_var(type=type, lb=lb, name=name)

        # decision vars
        self.vars.update(self.nodes[0].vars)
        self.conts.update(self.nodes[0].vars)
        self.bins.update(self.nodes[0].vars)
        self.ints.update(self.nodes[0].vars)
        # non-decision vars
        self.slacks.update(self.nodes[0].vars)
        self.surplus.update(self.nodes[0].vars)
        # update model constrs
        self.constrs = self.nodes[0].constrs[:]
        return self.nodes[0].vars[name]

    def add_constr(self, constr: LinConstr):
        """Adds a linear constraint, and add slack and surplus variables as needed."""
        self.nodes[0].add_constr(constr)
        self.constrs = self.nodes[0].constrs[:]

    def set_objective(self, objexpr: LinExpr, sense='min'):
        """Sets objective."""
        self.nodes[0].set_objective(objexpr, sense=sense)
        self.objexpr = objexpr
        if sense == 'max':
            self.sense = 'max'
            self.objval = -math.inf
            self.icmbval = -math.inf

    def describe(self):
        """Describes the linear program."""
        print('{}\t{}'.format(self.sense, self.objexpr))
        for idx, constr in enumerate(self.constrs):
            if idx == 0:
                print('st\t{}'.format(constr))
            else:
                print('\t{}'.format(constr))

    def candidates_queue(self):
        """Returns a queue of candidate nodes in the order of processing."""
        return [*self.candidates]

    def optimize(self, verbose=False):
        """Optimizes the mixed integer programming model."""
        while self.code == -1:
            if self.candidates_queue():
                key = self.candidates_queue()[0]
                node = self.nodes[key]
                node.optimize(verbose=verbose)

                # print('\nNode {}'.format(node.key))
                # node.describe()
                # if node.code == 0:
                #     print(', '.join(str(node.vars[key].val) for key in self.vars.keys()))
                #     print('Objval: {}'.format(node.objval))
                # else:
                #     print(node.code)

                # found a solution
                if node.code == 0:
                    # branch or bound
                    frac_vars = [*node.ints.values()] + [*node.bins.values()]
                    var_opts = []
                    for var in frac_vars:
                        if not float(var.val).is_integer():
                            var_opts.append(var)

                    # fractional solution
                    if var_opts:
                        # branch
                        if (self.sense == 'max' and node.objval > self.icmbval) or (self.sense == 'min' and node.objval < self.icmbval):
                            del self.candidates[key]
                            var = var_opts[0]
                            # branch down
                            left_node = copy.deepcopy(node)
                            left_node.key = len(self.nodes)
                            left_node.code = -1
                            left_node.add_constr(var <= math.floor(var.val))
                            left_node.set_objective(self.objexpr, sense=self.sense)
                            self.nodes[left_node.key] = left_node
                            self.candidates[left_node.key] = left_node
                            # branch up
                            right_node = copy.deepcopy(node)
                            right_node.key = len(self.nodes)
                            right_node.code = -1
                            right_node.add_constr(var >= math.ceil(var.val))
                            right_node.set_objective(self.objexpr, sense=self.sense)
                            self.nodes[right_node.key] = right_node
                            self.candidates[right_node.key] = right_node
                        # bound
                        else:
                            del self.candidates[key]
                    # integral solution
                    else:
                        del self.candidates[key]
                        # update incumbent value
                        if (self.sense == 'max' and node.objval > self.icmbval) or (self.sense == 'min' and node.objval < self.icmbval):
                            self.icmbkey = node.key
                            self.icmbval = node.objval

                # unbounded: terminate optimization
                elif node.code == 1:
                    self.code = 1
                # infeasible:
                elif node.code == 2:
                    del self.candidates[key]
            # no more candidates
            else:
                self.code = 0
        # finishing
        if self.code == 0:
            self.objkey = self.icmbkey
            self.objval = self.icmbval
            for key in self.vars.keys():
                self.vars[key].val = self.nodes[self.objkey].vars[key].val
            print('\nOptimal objective value: {}'.format(self.objval))
        elif self.code == 1:
            print('Model unbounded')


if __name__ == '__main__':
    m = Model()
    x = m.add_var(type='int', name='x')
    y = m.add_var(type='bin', name='y')
    m.add_constr(3*x + 5*y <= 78.8)
    m.add_constr(4*x + y <= 36.5)
    m.set_objective(5*x + 4*y, sense='max')
    m.describe()
    m.optimize(True)

    if m.code == 0:
        print('\nObjective value:{}'.format(m.objval))
        for var in m.vars.values():
            print("{}({}): {}".format(var.name, var.type, var.val))
    elif m.code == 1:
        print('Model unbounded')
    elif m.code == 2:
        print('Model infeasible')