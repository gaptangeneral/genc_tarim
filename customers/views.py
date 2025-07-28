from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from django.http import JsonResponse

from .models import Customer
from service.models import ServiceRecord

from .forms import CustomerForm,QuickCustomerForm

class CustomerListView(LoginRequiredMixin, ListView):
    permission_required = 'customers.view_customer'

    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Müşteriler"
        return context

class CustomerDetailView(LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        context['page_title'] = customer.get_display_name()
        # Müşteriye ait servis kayıtlarını alıp context'e ekliyoruz
        context['service_records'] = ServiceRecord.objects.filter(customer=customer).order_by('-created_at')
        return context

class CustomerCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    permission_required = 'customers.add_customer'

    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    permission_required = 'customers.add_customer'
    success_message = "Müşteri başarıyla oluşturuldu."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Müşteri Ekle"
        return context

    def get_success_url(self):
        return reverse_lazy('customers:customer_list')

class CustomerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    permission_required = 'customers.change_customer'

    model = Customer
    form_class = CustomerForm
    template_name = 'customers/customer_form.html'
    permission_required = 'customers.change_customer'
    success_message = "Müşteri bilgileri başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.get_display_name()}" Müşterisini Düzenle'
        return context

    def get_success_url(self):
        return reverse_lazy('customers:customer_list')
    
@login_required
@require_POST
def add_customer_ajax(request):
    form = QuickCustomerForm(request.POST)
    if form.is_valid():
        customer = form.save()
        return JsonResponse({'id': customer.id, 'name': customer.get_display_name()})
    else:
        # Form hatalarını JSON olarak döndür
        return JsonResponse({'error': form.errors.as_json()}, status=400)
