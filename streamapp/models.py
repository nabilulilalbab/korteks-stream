from django.db import models

# Create your models here.

class Advertisement(models.Model):
    """
    Model untuk menyimpan iklan yang akan ditampilkan di halaman detail episode video.
    """
    PROVIDER_CHOICES = [
        ('propeller', 'PropellerAds'),
        ('adsterra', 'Adsterra'),
        ('popcash', 'PopCash'),
        ('custom', 'Custom'),
    ]
    
    POSITION_CHOICES = [
        ('above_player', 'Di atas player video'),
        ('below_player', 'Di bawah player video'),
        ('between_info', 'Di antara informasi anime'),
        ('sidebar', 'Di sidebar'),
        ('above_download', 'Di atas download links'),
        ('between_download', 'Di antara download links'),
        ('footer', 'Di footer'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nama Iklan")
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, verbose_name="Penyedia Iklan")
    ad_code = models.TextField(verbose_name="Kode Iklan (HTML/JavaScript)")
    position = models.CharField(max_length=20, choices=POSITION_CHOICES, verbose_name="Posisi Iklan")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    priority = models.IntegerField(default=0, verbose_name="Prioritas (semakin tinggi semakin diprioritaskan)")
    max_width = models.CharField(max_length=20, blank=True, null=True, verbose_name="Lebar Maksimum (contoh: 100%, 300px)")
    max_height = models.CharField(max_length=20, blank=True, null=True, verbose_name="Tinggi Maksimum (contoh: auto, 250px)")
    start_date = models.DateTimeField(blank=True, null=True, verbose_name="Tanggal Mulai")
    end_date = models.DateTimeField(blank=True, null=True, verbose_name="Tanggal Berakhir")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Dibuat pada")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Diperbarui pada")
    
    class Meta:
        verbose_name = "Iklan"
        verbose_name_plural = "Iklan"
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        position_display = dict(self.POSITION_CHOICES).get(self.position, self.position)
        return f"{self.name} ({position_display})"
    
    def is_valid_date_range(self):
        """
        Memeriksa apakah iklan masih dalam rentang tanggal yang valid.
        """
        from django.utils import timezone
        now = timezone.now()
        
        if self.start_date and self.start_date > now:
            return False
        
        if self.end_date and self.end_date < now:
            return False
        
        return True
