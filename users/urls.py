from django.urls import path

from .views import user_list, user_edit, complete_onboarding, add_user # Import add_user

urlpatterns = [
    path('add/', add_user, name='user_add'), # Add URL for adding users
    path('', user_list, name="user_list"),
    path('<str:user_pk>/edit/', user_edit, name="user_edit"),
    path('complete-onboarding/', complete_onboarding, name='complete_onboarding'), # Add URL for onboarding
]
