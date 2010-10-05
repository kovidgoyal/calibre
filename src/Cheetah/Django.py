import Cheetah.Template

def render(template_file, **kwargs):
    '''
        Cheetah.Django.render() takes the template filename 
        (the filename should be a file in your Django 
        TEMPLATE_DIRS)

        Any additional keyword arguments are passed into the 
        template are propogated into the template's searchList
    '''
    import django.http
    import django.template.loader
    source, loader = django.template.loader.find_template_source(template_file)
    t = Cheetah.Template.Template(source, searchList=[kwargs])
    return django.http.HttpResponse(t.__str__())
