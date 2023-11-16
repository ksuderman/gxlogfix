
import graphviz


if __name__ == '__main__':
    g = graphviz.Digraph('G', filename='hello.gv')
    g.attr('node', shape='record')
    g.node('call', label='ast.Call')
    g.node('debug', label='{func|log.debug}')
    g.node('args', label='Args')
    g.edge('Hello', 'World')
    g.view()