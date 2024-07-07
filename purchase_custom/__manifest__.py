{
    'name': "Purchase Custom",
    'summary': """Modifications in purchases""",
    'author': "Tonny Velazquez Juarez",
    'category': 'purchase',
    'version': '16.0.1.0.2',
    'depends': ['purchase', 'hr','product',],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_department_views.xml',
        'views/purchase_order_form_employee_view.xml',
        'views/purcharse_order_user_custom_views.xml',
    ],
}
