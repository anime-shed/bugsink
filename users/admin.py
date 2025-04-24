from django.contrib import admin
import secrets
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, EmailVerification
from .tasks import send_welcome_email


# Define a custom UserAdmin
class UserAdmin(BaseUserAdmin):
    add_form_template = 'admin/auth/user/add_form.html' # Use default template initially
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username',), # Use 'username' as it maps to email in our setup
        }),
    )

    def add_view(self, request, form_url='', extra_context=None):
        if request.method == 'POST':
            form = self.get_form(request)(request.POST)
            if form.is_valid():
                email = form.cleaned_data['username']
                if User.objects.filter(username=email).exists():
                    messages.error(request, _('A user with that email already exists.'))
                else:
                    password = secrets.token_urlsafe(12) # Generate a secure random password
                    user = User.objects.create_user(username=email, email=email, password=password)
                    user.needs_onboarding = True
                    user.is_active = True # User must be active to login
                    user.save()

                    # Email sending logic removed.
                    # Display the temporary password directly to the admin.
                    messages.success(request, _(f'The user {email} was added successfully. Temporary password: {password}'))
                    return self.response_post_save_add(request, user)
        else:
            form = self.get_form(request)()

        context = self.get_changeform_initial_data(request)
        context.update({
            'title': _('Add user'),
            'form': form,
            'is_popup': False,
            'save_as': False,
            'has_delete_permission': False,
            'has_add_permission': True,
            'has_change_permission': False,
            'has_view_permission': False,
            'has_editable_inline_admin_formsets': False,
            'add': True,
            'change': False,
            'show_save': True,
            'show_save_and_continue': False,
            'show_save_and_add_another': False,
            **(extra_context or {}),
        })
        return self.render_change_form(request, context, form_url=form_url, add=True)

    # Ensure other necessary UserAdmin configurations are inherited or defined
    # For example, list_display, search_fields etc. might be needed for the admin interface
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'needs_onboarding')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    filter_horizontal = () # Add if needed for many-to-many fields like groups/permissions
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'needs_onboarding')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Onboarding'), {'fields': ('needs_onboarding',)}), # Add needs_onboarding here
    )


admin.site.register(User, UserAdmin)


admin.site.register(EmailVerification)
