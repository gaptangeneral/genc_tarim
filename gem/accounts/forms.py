from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User, Group,Permission

class CustomLoginForm(AuthenticationForm):
    """
    Giriş formunu, placeholder metinleri ve standart stilimizi içerecek şekilde özelleştirir.
    """
    username = forms.CharField(widget=forms.TextInput(attrs={
        'autofocus': True,
        'placeholder': 'Kullanıcı Adınız',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Şifreniz',
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
    }))

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-posta")
    first_name = forms.CharField(max_length=30, required=False, label="Adı")
    last_name = forms.CharField(max_length=30, required=False, label="Soyadı")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': original_style})

class UserUpdateForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Gruplar"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        original_style = 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        # Checkbox ve MultipleChoice alanları hariç diğerlerine stil uygula
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                field.widget.attrs.update({'class': original_style})
        
        # Checkbox'lar için özel stil
        for checkbox_field in ['is_active', 'is_staff', 'is_superuser']:
             if checkbox_field in self.fields:
                self.fields[checkbox_field].widget.attrs.update({'class': 'h-4 w-4 rounded border-gray-300 text-primary focus:ring-blue-500'})
                
class GroupForm(forms.ModelForm):
    # İzinleri, çoklu seçilebilen checkbox'lar olarak gösteriyoruz
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Bu Grubun Sahip Olduğu Yetkiler"
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # İsim alanı için standart stilimizi ekleyelim
        self.fields['name'].widget.attrs.update({
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500'
        })