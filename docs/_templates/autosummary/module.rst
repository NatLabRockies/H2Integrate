{{ fullname | escape | underline}}

.. automodule:: {{ fullname }}

   {% block attributes %}
   {% if attributes %}
   .. rubric:: {{ _('Module Attributes') }}

   .. autosummary::
   {% for item in attributes %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block functions %}
   {% if functions %}
   .. rubric:: {{ _('Functions') }}

   .. autosummary::
   {% for item in functions %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block classes %}
   {% if classes %}
   .. rubric:: {{ _('Classes') }}

   .. autosummary::
   {% for item in classes %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

   {% block exceptions %}
   {% if exceptions %}
   .. rubric:: {{ _('Exceptions') }}

   .. autosummary::
   {% for item in exceptions %}
      {{ item }}
   {%- endfor %}
   {% endif %}
   {% endblock %}

{% block modules %}
{# Filter out pytest conftest modules; they cannot be imported outside a
   pytest session (they use `from test.conftest import ...` which requires
   the repo-root ``test/`` package to be on ``sys.path``) and so autosummary
   raises "failed to import" warnings on them. #}
{% set filtered_modules = modules | reject('equalto', 'conftest') | list %}
{% if filtered_modules %}
.. rubric:: Modules

.. autosummary::
   :toctree:
   :recursive:
{% for item in filtered_modules %}
   {{ item }}
{%- endfor %}
{% endif %}
{% endblock %}
