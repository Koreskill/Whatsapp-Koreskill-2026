from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationViewsTests(TestCase):
    def setUp(self):
        self.password = "a-secure-test-password"
        self.user = get_user_model().objects.create_user(
            username="agente", password=self.password
        )

    def test_login_page_is_available(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ingresar")

    def test_valid_credentials_log_the_user_in(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": self.password},
        )

        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)

    def test_logout_requires_post_and_ends_the_session(self):
        self.client.force_login(self.user)

        get_response = self.client.get(reverse("logout"))
        post_response = self.client.post(reverse("logout"))

        self.assertEqual(get_response.status_code, 405)
        self.assertRedirects(post_response, reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)
