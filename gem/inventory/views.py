# inventory/views.py

# Gerekli Django modüllerini import ediyoruz
import json
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages
from django.db.models import Q, F, Sum, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

# Kendi uygulamamızdan modelleri ve formları import ediyoruz
from .models import Product, StockMovement, Category, Brand, Supplier
from .forms import CategoryForm, ProductSearchForm, ProductForm, QuickProductForm, StockMovementForm

# === GENEL AMAÇLI VIEW'LAR ===

class ReportsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'inventory.view_product'
    template_name = 'inventory/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Raporlar"
        total_value = Product.active_objects.annotate(
            line_total=Coalesce(F('quantity') * F('purchase_price'), Value(0), output_field=DecimalField())
        ).aggregate(
            total=Sum('line_total')
        )['total'] or 0
        context['total_inventory_value'] = total_value
        context['most_stocked_products'] = Product.active_objects.order_by('-quantity')[:5]
        context['latest_movements'] = StockMovement.objects.all().order_by('-timestamp')[:5]
        return context

# === ÜRÜN CRUD VIEW'LARI ===

class ProductListView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 15

    def get_queryset(self):
        queryset = Product.active_objects.select_related('category', 'brand').order_by('-created_at')
        query = self.request.GET.get('query')
        category = self.request.GET.get('category')
        brand = self.request.GET.get('brand')
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(product_code__icontains=query) | Q(barcode_data__icontains=query)
            )
        if category:
            queryset = queryset.filter(category__slug=category)
        if brand:
            queryset = queryset.filter(brand__slug=brand)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_products = Product.active_objects.all()
        low_stock_products_queryset = all_products.filter(quantity__gt=0, quantity__lte=F('min_stock_level'))
        out_of_stock_products_queryset = all_products.filter(quantity=0)
        context['stats'] = {
            'total_products': all_products.count(),
            'in_stock': all_products.count() - out_of_stock_products_queryset.count(),
            'low_stock': low_stock_products_queryset.count(),
            'out_of_stock': out_of_stock_products_queryset.count(),
            'out_of_stock_products': out_of_stock_products_queryset,
            'low_stock_products': low_stock_products_queryset
        }
        context['form'] = ProductSearchForm(self.request.GET)
        return context

class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        context['stock_movements'] = StockMovement.objects.filter(product=product).order_by('-timestamp')[:10]
        context['page_title'] = "Ürün Detayı"
        context['stock_movement_form'] = StockMovementForm()
        return context

    def post(self, request, *args, **kwargs):
        product = self.get_object()
        form = StockMovementForm(request.POST)
        if form.is_valid():
            new_movement = form.save(commit=False)
            new_movement.product = product
            new_movement.user = request.user
            new_movement.save()
            messages.success(request, 'Stok hareketi başarıyla eklendi.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return redirect('inventory:product_detail', slug=product.slug)

class ProductLabelPrintView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'inventory/product_label_print.html'
    context_object_name = 'product'

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    permission_required = 'inventory.add_product'
    success_message = "Yeni ürün başarıyla oluşturuldu."
    success_url = reverse_lazy('inventory:product_list')

    def form_valid(self, form):
        initial_stock = form.cleaned_data.get('initial_stock', 0)
        response = super().form_valid(form)
        if initial_stock and initial_stock > 0:
            StockMovement.objects.create(
                product=self.object,
                movement_type='INITIAL_STOCK',
                quantity=initial_stock,
                user=self.request.user,
                notes="Ürün oluşturulurken girilen başlangıç stoku."
            )
            messages.info(self.request, f"{self.object.name} için {initial_stock} adet başlangıç stoku eklendi.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Ürün Ekle"
        return context

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    permission_required = 'inventory.change_product'
    success_message = "Ürün başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.name}" Ürününü Düzenle'
        return context

    def get_success_url(self):
        return reverse_lazy('inventory:product_detail', kwargs={'slug': self.object.slug})

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    permission_required = 'inventory.delete_product'
    success_url = reverse_lazy('inventory:product_list')
    context_object_name = 'product'
    
    def form_valid(self, form):
        messages.success(self.request, f'"{self.object.name}" adlı ürün başarıyla silindi.')
        return super().form_valid(form)

# === KATEGORİ CRUD VIEW'LARI ===

class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Category
    template_name = 'inventory/category_list.html'
    context_object_name = 'categories'
    permission_required = 'inventory.view_category'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Kategoriler"
        return context

class CategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    permission_required = 'inventory.add_category'
    success_url = reverse_lazy('inventory:category_list')
    success_message = "Yeni kategori başarıyla oluşturuldu."
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Yeni Kategori Ekle"
        return context

class CategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'inventory/category_form.html'
    permission_required = 'inventory.change_category'
    success_url = reverse_lazy('inventory:category_list')
    success_message = "Kategori başarıyla güncellendi."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'"{self.object.name}" Kategorisini Düzenle'
        return context

class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Category
    template_name = 'inventory/category_confirm_delete.html'
    success_url = reverse_lazy('inventory:category_list')
    permission_required = 'inventory.delete_category'
    
    def form_valid(self, form):
        messages.success(self.request, f'"{self.object.name}" kategorisi başarıyla silindi.')
        return super().form_valid(form)

# === AJAX VIEW'LARI ===

@login_required
@require_POST
def add_product_ajax(request):
    form = QuickProductForm(request.POST)
    if form.is_valid():
        product = form.save(commit=False)
        product.quantity = 0
        product.save()
        return JsonResponse({'id': product.id, 'name': product.name})
    else:
        return JsonResponse({'error': form.errors.as_json()}, status=400)

@login_required
@require_POST
def add_category_ajax(request):
    name = request.POST.get('name', None)
    if name:
        category, created = Category.objects.get_or_create(name=name)
        if created:
            return JsonResponse({'id': category.id, 'name': category.name})
    return JsonResponse({'error': 'İsim boş olamaz veya bu kategori zaten mevcut.'}, status=400)

@login_required
@require_POST
def add_brand_ajax(request):
    name = request.POST.get('name', None)
    if name:
        brand, created = Brand.objects.get_or_create(name=name)
        if created:
            return JsonResponse({'id': brand.id, 'name': brand.name})
    return JsonResponse({'error': 'İsim boş olamaz veya bu marka zaten mevcut.'}, status=400)

@login_required
@require_POST
def add_supplier_ajax(request):
    name = request.POST.get('name', None)
    if name:
        supplier, created = Supplier.objects.get_or_create(name=name)
        if created:
            return JsonResponse({'id': supplier.id, 'name': supplier.name})
    return JsonResponse({'error': 'İsim boş olamaz veya bu tedarikçi zaten mevcut.'}, status=400)