from django.db import models

class CsvRow(models.Model):
    date = models.DateField(null=True, blank=True)
    text = models.TextField()
    sentiment = models.CharField(max_length=20)
    score = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.date} - {self.sentiment}"

# Create your models here.
