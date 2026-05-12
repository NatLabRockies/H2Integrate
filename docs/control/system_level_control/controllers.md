# Control Strategies
There are several simple control strategies already implemented in the SLC paradigm. While fairly simplistic, they are meant to illustrate how information can be passed from different blocks/components (converters, storage, feedstocks, demand, etc.) and models (performance, cost, finance) to use within the SLC.

The current control strategies are:
1. [Demand Following](#slc-demand-following)
2. [Profit Maximization](#slc-profit-max)
3. [Cost Minimization](#slc-cost-min)

```{note}
The strategies currently implemented are experimental and will likely require further development for specific analyses.
```

All control strategies inherit `SystemLevelControlBase`, which is a base class that has common setup logic shared by all system-level control strategies.

See additional information, which is more developer focused, about the [`SystemLevelControlBase`](#slc-base).
