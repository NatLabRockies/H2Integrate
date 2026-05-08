# System Level Control Technology Performance Classifiers

To enable a generic system level control framework we need to classify each technology based on how the model, that is included in H2I, can operate within the system.

```{note}
While in real life there are a lot of controllable parameters allowing for ramping production up or down for a particular technology (e.g., turbine yaw). The particular model in H2I might not be capable of simulating a modulated response based on an input signal.
```

We have identified three key classifiers that are able to represent the different behaviors that we can expect from the model. Each performance model includes a parameter setting the classifier `_control_classifier`.

Classifier | Meaning | Example Techs
-- | -- | --
curtailable | Produces based on resource or input commodity; can only be reduced | wind, solar, nuclear
dispatchable | Can modulate consumption/production within bounds | grid, NG turbine
storage | Can modulate consumption/production within bounds while tracking SOC; does not produce/consume energy | battery, h2 storage, any storage

To add a classifier for a particular model it would look something like this in the class:
```{python}
_control_classifier = "curtailable"
```

## Curtailable
A curtailable performance model represents anything that can have the output reduced based on a give set point from the system level controller. This classifier and the inputs and outputs are included in the figure below. A good example of this is the PVWatts PySAM solar plant in H2I, the performance of the system is based on the input solar resource. The solar performance does not change based on, for example, an updated set point to the tracking software, but we could limit the power output from the solar performance model based on a given demand set point. To simplify the implementation of applying this curtailment or reduction based on a set point we added a method, `apply_curtailment()` to the `PerformanceBaseClass`.

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
Storage is a unique control classifier because it assumes that within the model that energy isn't created or destroyed (minus some efficiency losses). While it's technically "dispatchable" in that it can receive and change its performance based on a set point it's handling within H2I is unique because it's attached to storage performance models, which is handled differently than converter performance models.

The storage performance models that have the "storage" control classifier additionally require a storage-level controller in addition to the overarching system level controller. See the image below for reference. The storage-level controller takes in the system level-controller set points and outputs charge (negative) and discharge (positive) commands (storage-level set points) to the storage performance model.

ADD IMAGE - wait until [PR # 731](https://github.com/NatLabRockies/H2Integrate/pull/731) comes in.
