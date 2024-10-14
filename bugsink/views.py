from django.shortcuts import redirect
from django.conf import settings

from django.template.defaultfilters import filesizeformat
from django.views.decorators.http import require_GET
from django.views.decorators.cache import cache_control
from django.http import FileResponse, HttpRequest, HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render

from snappea.settings import get_settings as get_snappea_settings

from bugsink.version import __version__
from bugsink.decorators import login_exempt
from bugsink.app_settings import get_settings as get_bugsink_settings


def home(request):
    if request.user.project_set.filter(projectmembership__accepted=True).distinct().count() == 1:
        # if the user has exactly one project, we redirect them to that project
        project = request.user.project_set.get()
        return redirect("issue_list_open", project_pk=project.id)

    if request.user.project_set.all().distinct().count() > 0:
        # note: no filter on projectmembership__accepted=True here; if there is _any_ project, we show the project list
        return redirect("project_list")

    if get_bugsink_settings().SINGLE_TEAM:
        # in single-team mode, there's is no (meaningful) team list. We redirect to the (empty) project list instead
        return redirect("project_list")

    # final fallback: show the team list.
    # (the assumption is: if there are no projects, the team-list is the most useful page to show, because if there are
    # no teams, this is where you can create one, and if there are teams, this is where you can select one)
    return redirect("team_list")


@login_exempt
def trigger_error(request):
    raise Exception("Exception triggered on purpose to debug error handling")


@require_GET
@cache_control(max_age=60 * 60 * 24, immutable=True, public=True)
@login_exempt
def favicon(request: HttpRequest) -> HttpResponse:
    file = (settings.BASE_DIR / "static" / "favicon.png").open("rb")
    return FileResponse(file)


@user_passes_test(lambda u: u.is_superuser)
def settings_view(request):
    def get_setting(settings, key):
        value = getattr(settings, key, None)
        if key in ["EMAIL_HOST_PASSWORD", "EMAIL_HOST_USER"]:
            return "********" if value else ""
        return value

    def round_values(settings):
        def maybe_round(v):
            if isinstance(v, int) and v > 0 and v % 1024 == 0:
                return "%s (%s)" % (v, filesizeformat(v))
            return v
        return {k: maybe_round(v) for k, v in settings.items()}

    misc_settings = {
        k: get_setting(settings, k) for k in (
            "ALLOWED_HOSTS",
            "SECURE_PROXY_SSL_HEADER",
            "TIME_ZONE",
            "EMAIL_HOST",
            "EMAIL_HOST_USER",
            "EMAIL_HOST_PASSWORD",
            "EMAIL_PORT",
            "EMAIL_USE_TLS",
            "EMAIL_BACKEND",
            "DEFAULT_FROM_EMAIL",
        )
    }

    return render(request, "bugsink/settings.html", {
        "bugsink_settings": round_values(get_bugsink_settings()),
        "snappea_settings": get_snappea_settings(),
        "misc_settings": misc_settings,
        "version": __version__,
    })
