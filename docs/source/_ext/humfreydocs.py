
# Cribbed from Django's docs (BSD) so we can link to settings.
def setup(app):
    app.add_crossref_type(
        directivename = "setting",
        rolename = "setting",
        indextemplate = "pair: %s; setting",
    )
    app.add_crossref_type(
        directivename = "templatetag",
        rolename = "ttag",
        indextemplate = "pair: %s; template tag"
    )