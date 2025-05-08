from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import User
import os

class SentimentViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='pass1234')
        self.client.login(username='testuser', password='pass1234')

    def csv(self):
        csv_content = b"tweet\nThis is a great cat!\nI hate cats"
        file = SimpleUploadedFile("test.csv", csv_content, content_type="text/csv")
        response = self.client.post("/upload/", {'file': file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Results will be available shortly")

    def file_extension(self):
        file = SimpleUploadedFile("test.txt", b"not a csv", content_type="text/plain")
        response = self.client.post("/upload/", {'file': file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please upload a CSV file")

    def analysis_view_getresults(self):
        response = self.client.get("/analysis/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sentiment/analysis_results.html")
        self.assertContains(response, "Sentiment")

    def missing_file(self):
        response = self.client.post("/upload/", {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No file was uploaded")

    def post_upload(self):
        csv_content = b"tweet\nI Love Cats!\nI Hate Cats!"
        file = SimpleUploadedFile("sample.csv", csv_content, content_type="text/csv")
        response = self.client.post("/analysis/", {'csv_file': file})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sentiment Distribution")

