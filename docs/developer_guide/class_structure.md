# Class structure in H2Integrate

A major focus of H2Integrate is modularizing the components and system architecture so it's easier to construct and analyze complex hybrid power plants producing commodities for a variety of uses.
As such, we've taken great care to develop a series of base classes and inherited classes to help users develop their own models.

## Base classes

We previously discussed converters, transporters, and storage components.
These components each have an associated base class that contain the methods expected and used for each of those components.
These base classes live within the `core` directory of H2Integrate.

## Inherited classes

Individual technology classes could inherit directly from these base classes, but we do not encourage this within H2Integrate.
Instead, we have an additional layer of class inheritance that helps reduce duplicated code and potential errors.

Let us take a PEM electrolyzer model as an example.
Each electrolyzer model has shared methods and attributes that would be present in any valid model.
These methods are defined at the `ElectrolyzerBaseClass` level, which inherits from `ConverterBaseClass`.
Any implemented electrolyzer model should inherit from `ElectrolyzerBaseClass` to make use of its already built out structure and methods.

## Interactive class hierarchy

The diagram below shows **every model class** in H2Integrate and how they inherit from one another.
The visual encoding uses three dimensions:

- **Color** represents the application group (electricity, chemical, metal, etc.)
- **Shape** represents the model category (converter, storage, transporter, etc.)
- **Border thickness** indicates inheritance depth (thicker borders = higher-level parent classes)

Arrows point from parent to child.
You can **zoom**, **pan**, **hover** for details, and **drag** nodes to rearrange the layout.

To regenerate this visualization after code changes, run:

```bash
python docs/generate_class_hierarchy.py
```

```{raw} html
<div style="width:100%; box-sizing:border-box;">
  <iframe src="../_static/class_hierarchy.html" width="100%" height="950px"
          style="border:1px solid #ccc; border-radius:8px;"
          allowfullscreen></iframe>
</div>
```
