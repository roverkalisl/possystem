from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, QuotationItem, Item


class QuotationForm(forms.ModelForm):
    valid_until = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date', 'class': 'form-control'}))

    class Meta:
        model = Quotation
        fields = [
            'date', 'valid_until', 'customer_name', 'contact_person', 'phone', 'email', 'address', 'remarks', 'status'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class QuotationItemForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=Item.objects.filter(is_active=True).order_by('name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control quotation-item-select'})
    )

    class Meta:
        model = QuotationItem
        fields = ['item', 'item_code', 'description', 'qty', 'unit', 'unit_price', 'discount', 'line_total']
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'line_total': forms.NumberInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
        }


QuotationItemFormSet = inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    extra=1,
    can_delete=True
)
