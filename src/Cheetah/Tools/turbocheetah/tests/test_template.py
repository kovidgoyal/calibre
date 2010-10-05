import os
from turbocheetah import TurboCheetah

here = os.path.dirname(__file__)

values = {
    'v': 'VV',
    'one': 1,
    }

def test_normal():
    plugin = TurboCheetah()
    # Make sure a simple test works:
    s = plugin.render(values, template='turbocheetah.tests.simple1')
    assert s.strip() == 'This is a test: VV'
    # Make sure one template can inherit from another:
    s = plugin.render(values, template='turbocheetah.tests.import_inherit')
    assert s.strip() == 'Inherited: import'
    
def test_path():
    plugin = TurboCheetah()
    plugin.search_path = [here]
    # Make sure we pick up filenames (basic test):
    s = plugin.render(values, template_file='simple1')
    assert s.strip() == 'This is a test: VV'
    # Make sure we pick up subdirectories:
    s = plugin.render(values, template_file='sub/master')
    assert s.strip() == 'sub1: 1'

def test_search():
    plugin = TurboCheetah()
    plugin.search_path = [os.path.join(here, 'sub'),
                          os.path.join(here, 'sub2'),
                          here]
    # Pick up from third entry:
    s = plugin.render(values, template_file='simple1')
    assert s.strip() == 'This is a test: VV'
    # Pick up from sub/master, non-ambiguous:
    s = plugin.render(values, template_file='master')
    assert s.strip() == 'sub1: 1'
    # Pick up from sub/page, inherit from sub/template:
    s = plugin.render(values, template_file='page')
    assert s.strip() == 'SUB: sub content'
    # Pick up from sub2/page_over, inherit from sub/template:
    s = plugin.render(values, template_file='page_over')
    assert s.strip() == 'SUB: override content'
    # Pick up from sub/page_template_over, inherit from
    # sub2/template_over:
    s = plugin.render(values, template_file='page_template_over')
    assert s.strip() == 'OVER: sub content'
    # Change page, make sure that undoes overrides:
    plugin.search_path = [os.path.join(here, 'sub'),
                          here]
    s = plugin.render(values, template_file='page_over')
    assert s.strip() == 'SUB: sub content'

def test_string():
    # Make sure simple string evaluation works:
    plugin = TurboCheetah()
    s = plugin.render(values, template_string="""Hey $v""")
    assert s == "Hey VV"
    # Make sure a string can inherit from a file:
    plugin.search_path = [here]
    s = plugin.render(values, template_string="#extends inherit_from\ns value")
    assert s.strip() == 'inherit: s value'
    
