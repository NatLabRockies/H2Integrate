# Synthetic Aviation Fuel Model

The synthetic aviation fuel (SAF) model represents the production and costs of a
lignin-fed SAF plant. The model calculates SAF production from the plant's annual
nameplate capacity, capacity factor, and hourly availability of lignin feedstock.

The model is implemented in {mod}`h2integrate.converters.saf`. An example that
connects the SAF plant to a paper mill is provided in `examples/37_paper_mill/`.

## Production Model

The SAF plant receives lignin through the `lignin_in` commodity stream, with units
of kg/h. The default lignin consumption rate is 1,650 kg of lignin per tonne of
SAF. At each simulation time step, SAF production is limited by both the
configured operating rate of the plant and the amount of lignin available:

```{math}
	ext{capacity\_limited\_saf} =
\frac{\text{plant\_capacity\_mtpy} \times \text{capacity\_factor}}{8760}
```

```{math}
	ext{lignin\_limited\_saf} =
\frac{\text{lignin\_in}}{\text{lignin\_consumption}}
```

```{math}
	ext{saf\_out} = \min(\text{capacity\_limited\_saf}, \text{lignin\_limited\_saf})
```

This formulation ensures that the lignin consumed by the SAF plant cannot exceed
the lignin delivered through `lignin_in`. When sufficient lignin is available,
SAF production is limited by the plant capacity and capacity factor. When the
lignin supply is insufficient, SAF production decreases accordingly.

## Cost Model

The SAF cost model calculates capital expenditures, fixed operating expenditures,
and variable operating expenditures. Capital expenditures are proportional to the
plant's nameplate capacity. Fixed operating costs include capacity-dependent
expenses, property tax, and insurance.

Variable operating costs include:

- lignin
- raw water
- hydrogen
- salt mixture
- hydrogen chloride
- electricity
- wastewater disposal
- applicable transportation costs

The default cost assumptions use a 2023 cost year and can be replaced with
project-specific values through the technology configuration.

## Connection to a Paper Mill

The SAF model can receive lignin produced by a paper mill through the following
plant-level interconnection:

```yaml
technology_interconnections:
  - [paper_mill, saf, lignin, pipe]
```

The framework connects the paper mill's `lignin_out` profile to the SAF plant's
`lignin_in` profile. The SAF performance model then uses the connected profile
directly when calculating hourly SAF production. This provides both structural and
physical coupling between the two technologies: the plant configuration transfers
the commodity stream, and the SAF production equation constrains production using
that stream.

## Current Limitations

The current SAF model uses constant feedstock consumption and production ratios.
It does not represent startup, shutdown, ramping, minimum operating loads, lignin
storage, feedstock quality variation, or changes in conversion yield.

## API Reference

```{eval-rst}
.. autosummary::
   :nosignatures:

   h2integrate.converters.saf.SAFPerformanceModel
   h2integrate.converters.saf.SAFCostModel
```
