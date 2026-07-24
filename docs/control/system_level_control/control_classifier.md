# System Level Control Technology Performance Classifiers

To enable a generic system level control framework we need to classify each technology based on how the model that is included in H2I can operate within the system.

```{note}
While in real life there are a lot of controllable parameters allowing for ramping production up or down for a particular technology (e.g., wind or solar curtailment), the model of that technology in H2I might not be capable of the same response behavior to input signals.
These classifications are for specific H2I dispatch formulations and are based on how the models in H2I are implemented, **not always** on how the actual physical subsystem might operate.
This is a useful and necessary distinction that delineates different model capabilities clearly.
```

We have identified five key classifiers that are able to represent the different behaviors that we can expect from the models. Each performance model includes a parameter setting the classifier `_control_classifier`.

Classifier | Meaning | Example Technology Models
-- | -- | --
fixed | Always produces commodity and cannot be controlled or reduced; does not receive a set-point | classical nuclear
flexible | Resource-driven; can only be *reduced* (curtailed) below the resource-determined maximum via a set-point | wind, solar
dispatchable | Can modulate production within bounds in response to a set-point | grid, electrolyzer, NG turbine
storage | Can modulate consumption/production within bounds while tracking SOC | battery, h2 storage, any storage
feedstock | Are not directly controlled, but useful for SLC to make dispatch decisions | feedstocks

To add a classifier for a particular model it would look something like this in the class:
```python
_control_classifier = "flexible"
```

```{note}
**Flexible vs. dispatchable.** Both classifiers receive a `{commodity}_set_point` from the system-level controller, so the distinction is about *what the set-point can do*. A flexible model is a strictly more restricted case of a dispatchable one: the set-point can only *cap* the output below whatever the underlying resource (sun, wind, etc.) makes available. A dispatchable model, by contrast, can be ramped up or down anywhere within its operating bounds in direct response to the set-point.
```

## Fixed
A fixed performance model represents anything that always produces at its rated capacity and cannot be controlled or reduced by the system level controller. The SLC reads the output from a fixed technology and subtracts it from the demand, but does not send a set-point back to the technology. A good example of this is a classical nuclear plant model: it produces a constant output that the rest of the system must accommodate.

(flexible)=
## Flexible
A flexible performance model represents anything whose production is determined by an external resource (e.g., wind speed, solar irradiance) and that can only be *reduced* below that resource-determined maximum and never increased above it. The system-level controller sends a `{commodity}_set_point` that acts as an upper bound: when the resource-driven output exceeds the set-point, output is curtailed down to the set-point; otherwise, output is left at the resource-driven value. A good example is the PVWatts PySAM solar plant in H2I; its performance is a function of the input solar resource, and we cannot tell the sun to shine more, but we can curtail the panel output below the available solar production.

In other words, flexible is a strictly more restricted case of [dispatchable](#dispatchable): a dispatchable model can be ramped both up and down in response to a set-point, while a flexible model can only be ramped down.

To simplify the implementation of applying this curtailment we added a method, `apply_curtailment()`, to the `PerformanceBaseClass`.

```{figure} figures/flexible.png
:width: 70%
:align: center
```

### Apply curtailment based on set_point
Within the `compute()` method in the performance model you can apply the curtailment using the `apply_curtailment()` method.
```
self.apply_curtailment(outputs)
```
which applies curtailment to `{commodity}_out` based on `{commodity}_set_point`. This adds `uncurtailed_{commodity}_out` and `{commodity}_out` as outputs from the performance model.

(dispatchable)=
## Dispatchable
A dispatchable performance model represents anything that can be ramped both *up and down* within its operating bounds in response to a `{commodity}_set_point` from the system-level controller. Unlike a [flexible](#flexible) model, the set-point for a dispatchable model can request any production level within the model's rated capacity (and minimum load, if applicable), and the model will produce at that level. Examples include a grid connection, an electrolyzer, or a natural-gas turbine.

There aren't additional special methods to handle this because the set-point response is internal to each performance model.

```{figure} figures/dispatchable.png
:width: 70%
:align: center
```

## Storage
Storage is a unique control classifier because it assumes that within the model that energy isn't created or destroyed (minus some efficiency losses). While it's technically "dispatchable" in that it can receive and change its performance based on a set point, its handling within H2I is unique because it's attached to storage performance models, which is handled differently than converter performance models. A converter model only has positive (or zero) `{commodity}_out`, whereas a storage model can have positive or negative `{commodity}_out`.

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
Feedstocks represent commodity *inputs* to the controllable system: they are consumed by other technologies but their availability is not itself something the controller can adjust. Although feedstocks themselves cannot be dispatched, knowing how much of each feedstock is available is valuable information for more advanced controllers, since feedstock supply can constrain what the controllable technologies are actually able to produce.

For example, consider an ammonia plant that consumes both hydrogen and nitrogen. If the nitrogen feedstock supply is insufficient to meet the ammonia demand, the ammonia output is capped by the nitrogen availability regardless of how much hydrogen and electricity are produced. A controller that is aware of the nitrogen feedstock can recognize that the ammonia demand cannot be met, and can adjust the set-points for the hydrogen and electricity technologies accordingly (e.g., avoiding over-production of hydrogen that would otherwise go unused). This is why feedstocks are classified separately rather than being ignored by the controller: they are uncontrollable, but they are not irrelevant.
