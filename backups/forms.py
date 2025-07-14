from django import forms

class RestoreForm(forms.Form):
    backup_file = forms.FileField(label="Yedekleme Dosyası (.zip)")