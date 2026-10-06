# Paper Mill Model

The paper mill model represents paper, pulp, and lignin production at an integrated
paper mill. Paper is the primary product, while pulp and lignin are additional
output streams that can be connected to other technologies in an H2Integrate plant
configuration.

The model is implemented in {mod}`h2integrate.converters.paper_mill`. An example
that connects the paper mill to a sustainable aviation fuel (SAF) plant is provided
in `examples/37_paper_mill/`.

## Production Model

The performance model calculates paper production from the mill's annual nameplate
capacity and capacity factor:

```{math}
	ext{annual paper production} =
	ext{plant\_capacity\_mtpy} \times \text{capacity\_factor}
```

The default co-product yields are:

| Output | Default yield | Output variable | Units |
| --- | ---: | --- | --- |
| Paper | 1.0 tonne per tonne of paper capacity | `paper_out` | t/h |
| Pulp | 1.1 tonnes per tonne of paper | `pulp_out` | t/h |
| Lignin | 0.06 tonnes per tonne of paper | `lignin_out` | kg/h |

These values produce hourly output profiles over the configured simulation period.
Changing the paper mill capacity, capacity factor, or yield inputs changes the
available product and co-product streams.

## Cost Model

The cost model calculates capital expenditures, fixed operating expenditures, and
variable operating expenditures. Capital expenditures scale with the mill's
nameplate capacity. Fixed operating costs include capacity-dependent expenses,
property tax, and insurance.

Variable operating costs include:

- wood
- raw water
- electricity
- wastewater disposal
- calcium carbonate
- sodium sulfide
- sodium hydroxide
- chlorine dioxide
- hydrogen peroxide
- magnesium sulfate
- oxygen
- applicable transportation costs

The default cost assumptions use a 2023 cost year. Project-specific assumptions can
be supplied through the technology configuration.

## Lignin Output

The paper mill exposes lignin as an hourly commodity stream named `lignin_out`, with
units of kg/h. This stream can be connected to a downstream technology that accepts
a `lignin_in` input.

For example, the following plant-level interconnection supplies paper mill lignin to
a SAF plant:

```yaml
technology_interconnections:
  - [paper_mill, saf, lignin, pipe]
```

For this connection, H2Integrate associates the `lignin` commodity with the paper
mill's `lignin_out` output and the SAF plant's `lignin_in` input. Assuming that the
selected connection model does not introduce material losses, the delivered lignin
profile satisfies:

```{math}
	ext{saf.lignin\_in} = \text{paper\_mill.lignin\_out}
```

The lignin stream is time dependent, so changes in paper mill capacity or capacity
factor affect both lignin availability and the operation of connected
lignin-consuming technologies.

## Current Limitations

The current paper mill model uses constant production ratios. It does not represent
startup, shutdown, ramping, minimum operating loads, intermediate product storage,
or changes in product yield.

## API Reference

```{eval-rst}
.. autosummary::
   :nosignatures:

   h2integrate.converters.paper_mill.PaperMillPerformanceModel
   h2integrate.converters.paper_mill.PaperMillCostModel
```
