# System Level Control Technology Performance Classifiers

To enable a generic system level control framework we need to classify each technology based on how the model, that is included in H2I, can operate within the system.

```{note}
While in real life there are a lot of controllable parameters allowing for ramping production up or down for a particular technology (e.g., turbine yaw). The particular model in H2I might not be capable of simulating a modulated response based on an input signal.
These classifications are for how the models in H2I are implemented, **not** how the actual physical subsystem might operate.
This is a useful and necessary distinction that delineates different model capabilities clearly.
```

We have identified five key classifiers that are able to represent the different behaviors that we can expect from the models. Each performance model includes a parameter setting the classifier `_control_classifier`.

Classifier | Meaning | Example Technology Models
-- | -- | --
fixed | Always produces commodity and cannot be controlled or reduced; does not receive a set-point | classical nuclear
flexible | Produces based on resource; can only reduce (curtail) | wind, solar
dispatchable | Can modulate consumption/production within bounds; receives a commodity set-point | grid, electrolyzer, NG turbine
storage | Can modulate consumption/production within bounds while tracking SOC | battery, h2 storage, any storage
feedstock | Are not directly controlled, but useful for SLC to know about to make dispatch decisions | feedstocks

To add a classifier for a particular model it would look something like this in the class:
```{python}
_control_classifier = "flexible"
```

## Fixed
A fixed performance model represents anything that always produces at its rated capacity and cannot be controlled or reduced by the system level controller. The SLC reads the output from a fixed technology and subtracts it from the demand, but does not send a set-point back to the technology. A good example of this is a classical nuclear plant model — it produces a constant output that the rest of the system must accommodate.

## Flexible
A flexible performance model represents anything that can have the output reduced based on a given set point from the system level controller. A good example of this is the PVWatts PySAM solar plant in H2I, the performance of the system is based on the input solar resource. The solar performance does not change based on, for example, an updated set point to the tracking software, but we could limit the power output from the solar performance model based on a given demand set point. To simplify the implementation of applying this curtailment or reduction based on a set point we added a method, `apply_curtailment()` to the `PerformanceBaseClass`.

```{figure} figures/curtailable.png
:width: 70%
:align: center
```

### Apply curtailment based on set_point
Within the `compute()` method in the performance model you can apply the curtailment using the `apply_curtailment()` method.
```
self.apply_curtailment(outputs)
```
which, applies curtailment to `{commodity}_out` based on `{commodity}_set_point`. There is then `uncurtailed_{commodity}_out` and `{commodity}_out` as outputs from the performance model.

## Dispatchable
A dispatchable performance model represents anything that can receive a set point. Any model that has the "dispatchable" control classifier tag is able to receive a set point and change it's behavior based on that set point. There aren't additional special methods to handle this because it's internal to each performance model.

```{figure} figures/dispatchable.png
:width: 70%
:align: center
```

## Storage
Storage is a unique control classifier because it assumes that within the model that energy isn't created or destroyed (minus some efficiency losses). While it's technically "dispatchable" in that it can receive and change its performance based on a set point it's handling within H2I is unique because it's attached to storage performance models, which is handled differently than converter performance models. A converter model only has positive (or zero) `{commodity}_out`, whereas a storage model can have positive or negative `{commodity}_out`.

There are two types of cases for the storage control classifier:
1. **with a storage controller**
When the storage performance model is controlled with a storage-level controller (open-loop or feedback controlled), the system-level controller outputs combined demand, that is always positive to the storage-level controller. The demand is `{commodity}_in` from the technologies upstream of the storage that output the same commodity to the storage performance model and the `remaining_demand`.

2. **without a storage controller**
The system-level controller outputs set points to the storage performance model which can be considered charge (negative) and discharge (positive) commands (storage-level set points) to the storage performance model, directly.


```{figure} figures/storage.png
:width: 85%
:align: center
```

## Feedstock
Another category of control classifiers are feedstocks. The unique thing about feedstocks is that they are considered outside of the controllable system within H2I. While they can't be controlled it can be helpful for controllers to know how much feedstock is available within the system, hence their classification.
