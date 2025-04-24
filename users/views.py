from datetime import timedelta

from django.contrib.auth import login
from django.shortcuts import render, redirect, reverse
from django.contrib.auth import get_user_model
from django.http import Http404
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

from bugsink.app_settings import get_settings, CB_ANYBODY
from bugsink.decorators import atomic_for_request_method

from .forms import (
    UserCreationForm, ResendConfirmationForm, RequestPasswordResetForm, SetPasswordForm, PreferencesForm, UserEditForm)
from .models import EmailVerification
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

from django.contrib.auth import login, update_session_auth_hash # Import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

from .tasks import send_confirm_email, send_reset_email
from .forms import AddUserForm # Import the new form
from django.contrib.auth.hashers import make_password
import secrets
import string


User = get_user_model()


@atomic_for_request_method
@user_passes_test(lambda u: u.is_superuser)
def user_list(request):
    users = User.objects.all().order_by('username')

    if request.method == 'POST':
        full_action_str = request.POST.get('action')
        action, user_pk = full_action_str.split(":", 1)
        if action == "deactivate":
            user = User.objects.get(pk=user_pk)
            user.is_active = False
            user.save()

            messages.success(request, 'User %s deactivated' % user.username)
            return redirect('user_list')

        if action == "activate":
            user = User.objects.get(pk=user_pk)
            user.is_active = True
            user.save()

            messages.success(request, 'User %s activated' % user.username)
            return redirect('user_list')

        if action == "delete":
            user = User.objects.get(pk=user_pk)
            if user.is_active:
                messages.error(request, 'Cannot delete active user %s' % user.username)
            else:
                username = user.username
                user.delete()
                messages.success(request, 'User %s deleted' % username)
            return redirect('user_list')

    return render(request, 'users/user_list.html', {
        'users': users,
    })


@atomic_for_request_method
@user_passes_test(lambda u: u.is_superuser)
def user_edit(request, user_pk):
    user = User.objects.get(pk=user_pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            return redirect("user_list")

    else:
        form = UserEditForm(instance=user)

    return render(request, "users/user_edit.html", {"form": form})


@atomic_for_request_method
@user_passes_test(lambda u: u.is_superuser)
def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            # Generate a secure temporary password
            alphabet = string.ascii_letters + string.digits + string.punctuation
            temp_password = ''.join(secrets.choice(alphabet) for i in range(12)) # 12-character password

            user = User.objects.create(
                username=email,
                email=email,
                password=make_password(temp_password), # Hash the password
                is_active=True, # User is active immediately
                needs_onboarding=True # User needs to set their own password
            )
            messages.success(request, f'User {email} created successfully. Temporary password: {temp_password}')
            return redirect('user_list')
    else:
        form = AddUserForm()

    return render(request, 'users/add_user.html', {'form': form})


# Custom Login View to handle onboarding redirection
def custom_login(request, *args, **kwargs):
    if request.user.is_authenticated and request.user.needs_onboarding:
        # If user is already logged in but needs onboarding, redirect them immediately
        return redirect('complete_onboarding')

    response = auth_views.LoginView.as_view(template_name="bugsink/login.html")(request, *args, **kwargs)

    # Check if login was successful and user needs onboarding
    if request.user.is_authenticated and request.user.needs_onboarding:
        # Clear any messages set by LoginView (like success message)
        storage = messages.get_messages(request)
        storage.used = True
        # Redirect to onboarding page
        messages.info(request, 'Please complete your profile and set a new password.')
        return redirect('complete_onboarding')

    return response


@login_required
@atomic_for_request_method
def complete_onboarding(request):
    user = request.user
    if not user.needs_onboarding:
        # If user somehow lands here but doesn't need onboarding, redirect them home.
        return redirect('home')

    if request.method == 'POST':
        # Use SetPasswordForm to enforce password rules
        # We could create a combined form if other fields (like first/last name) are required
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save() # Saves the new password
            user.needs_onboarding = False
            user.save(update_fields=['needs_onboarding'])
            messages.success(request, 'Your profile has been updated successfully.')
            # Log the user in again with the new password session if needed, though SetPasswordForm might handle this.
            # Re-login might be necessary depending on how session invalidation works with password changes.
            login(request, user) # Ensure user stays logged in
            return redirect('home') # Redirect to home page after successful onboarding
    else:
        form = SetPasswordForm(user)

    return render(request, 'users/complete_onboarding.html', {'form': form})


@atomic_for_request_method
def signup(request):
    if get_settings().USER_REGISTRATION != CB_ANYBODY:
        raise Http404("User self-registration is not allowed.")

    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            if get_settings().USER_REGISTRATION_VERIFY_EMAIL:
                user = form.save(commit=False)
                user.is_active = False
                user.save()

                verification = EmailVerification.objects.create(user=user, email=user.username)
                send_confirm_email.delay(user.username, verification.token)

                return render(request, "users/confirm_email_sent.html", {"email": user.username})

            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, "signup.html", {"form": form})


@atomic_for_request_method
def confirm_email(request, token=None):
    # clean up expired tokens; doing this on every request is just fine, it saves us from having to run a cron job-like
    EmailVerification.objects.filter(
        created_at__lt=timezone.now() - timedelta(get_settings().USER_REGISTRATION_VERIFY_EMAIL_EXPIRY)).delete()

    try:
        verification = EmailVerification.objects.get(token=token)
    except EmailVerification.DoesNotExist:
        # good enough (though a special page might be prettier)
        raise Http404("Invalid or expired token")

    if request.method == 'POST':
        # We insist on POST requests to do the actual confirmation (at the cost of an extra click). See:
        # https://softwareengineering.stackexchange.com/a/422579/168778
        # there's no Django form (fields), there's just a button to generate the post request

        verification.user.is_active = True
        verification.user.save()
        verification.delete()

        # this mirrors the approach of what we do in password-resetting; and rightfully so because the in both cases
        # access to email is assumed to be sufficient proof of identity.
        login(request, verification.user)

        return redirect('home')

    return render(request, "users/confirm_email.html")


@atomic_for_request_method
def resend_confirmation(request):
    if request.method == 'POST':
        form = ResendConfirmationForm(request.POST)

        if form.is_valid():
            user = User.objects.get(username=form.cleaned_data['email'])
            if user.is_active:
                raise Http404("This email is already confirmed.")

            verification = EmailVerification.objects.create(user=user, email=user.username)
            send_confirm_email.delay(user.username, verification.token)
            return render(request, "users/confirm_email_sent.html", {"email": user.username})
    else:
        form = ResendConfirmationForm(data=request.GET)

    return render(request, "users/resend_confirmation.html", {"form": form})


@atomic_for_request_method
def request_reset_password(request):
    # something like this exists in Django too; copy-paste-modify from the other views was more simple than thoroughly
    # understanding the Django implementation and hooking into it.

    if request.method == 'POST':
        form = RequestPasswordResetForm(request.POST)

        if form.is_valid():
            user = User.objects.get(username=form.cleaned_data['email'])
            # if not user.is_active  no separate branch for this: password-reset implies email-confirmation

            # we reuse the EmailVerification model for password resets; security wise it doesn't matter, because the
            # visiting any link with the token implies control over the email account; and we have defined that such
            # control implies both verification and password-resetting.
            verification = EmailVerification.objects.create(user=user, email=user.username)
            send_reset_email.delay(user.username, verification.token)
            return render(request, "users/reset_password_email_sent.html", {"email": user.username})

    else:
        form = RequestPasswordResetForm()

    return render(request, "users/request_reset_password.html", {"form": form})


@atomic_for_request_method
def reset_password(request, token=None):
    # alternative name: set_password (because this one also works for initial setting of a password)

    # clean up expired tokens; doing this on every request is just fine, it saves us from having to run a cron
    # job-like thing
    EmailVerification.objects.filter(
        created_at__lt=timezone.now() - timedelta(get_settings().USER_REGISTRATION_VERIFY_EMAIL_EXPIRY)).delete()

    try:
        verification = EmailVerification.objects.get(token=token)
    except EmailVerification.DoesNotExist:
        # good enough (though a special page might be prettier)
        raise Http404("Invalid or expired token")

    user = verification.user
    next_url = request.POST.get("next", request.GET.get("next", reverse("home")))

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            user.is_active = True  # password-reset implies email-confirmation
            user.set_password(form.cleaned_data['new_password1'])
            user.save()

            verification.delete()

            login(request, verification.user)

            return redirect(next_url)

    else:
        form = SetPasswordForm(user)

    return render(request, "users/reset_password.html", {"form": form, "next": next_url})


@atomic_for_request_method
# in the general case this is done by Middleware but we're under /accounts/, so we need it back.
# not security-critical because we simply get a failure on request.user if this wasn't there, but still the right thing.
@login_required
def preferences(request):
    user = request.user
    if request.method == 'POST':
        form = PreferencesForm(request.POST, instance=user)

        if form.is_valid():
            form.save()
            messages.success(request, "Updated preferences")
            return redirect('preferences')

    else:
        form = PreferencesForm(instance=user)

    return render(request, 'users/preferences.html', {
        'form': form,
    })


DEBUG_CONTEXTS = {
    "confirm_email": {
        "site_title": get_settings().SITE_TITLE,
        "base_url": get_settings().BASE_URL + "/",
        "confirm_url": "http://example.com/confirm-email/1234567890abcdef",  # nonsense to avoid circular import
    },
    "reset_password_email": {
        "site_title": get_settings().SITE_TITLE,
        "base_url": get_settings().BASE_URL + "/",
        "reset_url": "http://example.com/reset-password/1234567890abcdef",  # nonsense to avoid circular import
    },
}


@atomic_for_request_method
def debug_email(request, template_name):
    return render(request, 'mails/' + template_name + ".html", DEBUG_CONTEXTS[template_name])
