from django.db import models

class Customer(models.Model):
    # نفس from_number (whatsapp:+962...)
    user_key = models.CharField(max_length=64, unique=True)

    first_name = models.CharField(max_length=64)
    meter_last4 = models.CharField(max_length=4)

    phone = models.CharField(max_length=32, blank=True, default="")
    address = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} ({self.user_key})"


class ConsumptionRecord(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="consumptions")
    kwh = models.IntegerField()
    saving_percent = models.IntegerField(default=0)  # 18 يعني 18%
    period_label = models.CharField(max_length=32, default="هذا الشهر")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer.first_name} - {self.kwh}kWh"


class Complaint(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="complaints")
    text = models.TextField()
    status = models.CharField(max_length=32, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.id} {self.customer.first_name} {self.status}"
