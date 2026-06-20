from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet
from .models import Quotation, QuotationItem, Item


class QuotationForm(forms.ModelForm):
    date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': 'required'})
    )
    valid_until = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'required': 'required'})
    )
    customer_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'required': 'required'})
    )
    contact_person = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})
    )
    status = forms.ChoiceField(
        required=True,
        choices=Quotation.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control', 'required': 'required'})
    )

    class Meta:
        model = Quotation
        fields = [
            'date', 'valid_until', 'customer_name', 'contact_person', 'phone', 'email', 'address', 'remarks', 'status'
        ]

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('customer_name'):
            self.add_error('customer_name', 'Customer Name is required.')
        if not cleaned_data.get('valid_until'):
            self.add_error('valid_until', 'Valid Until Date is required.')
        if not cleaned_data.get('date'):
            self.add_error('date', 'Quotation Date is required.')
        return cleaned_data


class QuotationItemForm(forms.ModelForm):
    item = forms.ModelChoiceField(
        queryset=Item.objects.filter(is_active=True).order_by('name'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control quotation-item-select'})
    )
    qty = forms.DecimalField(
        required=False,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'})
    )
    unit_price = forms.DecimalField(
        required=False,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'})
    )

    class Meta:
        model = QuotationItem
        fields = ['item', 'item_code', 'description', 'qty', 'unit', 'unit_price', 'discount', 'line_total']
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'line_total': forms.NumberInput(attrs={'readonly': 'readonly', 'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        qty = cleaned_data.get('qty')
        unit_price = cleaned_data.get('unit_price')

        if not item and (qty or unit_price or cleaned_data.get('description') or cleaned_data.get('item_code')):
            self.add_error('item', 'Item selection is required.')
        if item and qty is None:
            self.add_error('qty', 'Quantity is required.')
        elif qty is not None and qty <= 0:
            self.add_error('qty', 'Quantity must be greater than zero.')
        if item and unit_price is None:
            self.add_error('unit_price', 'Unit Price is required.')
        elif unit_price is not None and unit_price <= 0:
            self.add_error('unit_price', 'Unit Price must be greater than zero.')
        return cleaned_data


class RequiredQuotationItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        valid_items = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                has_item = bool(form.cleaned_data.get('item'))
                has_qty = form.cleaned_data.get('qty') not in (None, '')
                has_price = form.cleaned_data.get('unit_price') not in (None, '')
                if has_item or has_qty or has_price:
                    valid_items += 1

        if valid_items == 0:
            raise ValidationError('Please add at least one quotation item.')


QuotationItemFormSet = inlineformset_factory(
    Quotation,
    QuotationItem,
    form=QuotationItemForm,
    formset=RequiredQuotationItemFormSet,
    extra=1,
    can_delete=True
)


# =========================
# PROJECT COST ANALYSIS
# =========================
from .models import ProjectBudget, ProjectBudgetLine, Project, GLMaster


class BudgetUploadForm(forms.Form):
    """Form for uploading project budgets via Excel"""
    
    project = forms.ModelChoiceField(
        queryset=Project.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Project',
        help_text='Select the project for which to import budget'
    )
    
    budget_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
        label='Budget File (Excel)',
        help_text='Upload an Excel file with columns: GL Code, GL Name, Budget Amount'
    )
    
    replace_existing = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Replace existing budget',
        help_text='Check to replace the entire existing budget'
    )

    create_missing_gl = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Create missing GL accounts',
        help_text='If enabled, GLs not found in the system will be created automatically (as Expense type)'
    )

    import_multiple_projects = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Import multiple projects from file',
        help_text='If enabled, the Excel file may include a Project/Project ID column to update budgets for multiple projects.'
    )


class ProjectBudgetForm(forms.ModelForm):
    """Form for creating/editing project budgets"""
    
    class Meta:
        model = ProjectBudget
        fields = ['project', 'budget_date', 'status', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-control'}),
            'budget_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }


class ProjectBudgetLineForm(forms.ModelForm):
    """Form for individual budget line items"""
    
    class Meta:
        model = ProjectBudgetLine
        fields = ['gl_account', 'budget_amount']
        widgets = {
            'gl_account': forms.Select(attrs={'class': 'form-control'}),
            'budget_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


ProjectBudgetLineFormSet = inlineformset_factory(
    ProjectBudget,
    ProjectBudgetLine,
    form=ProjectBudgetLineForm,
    extra=1,
    can_delete=True
)
