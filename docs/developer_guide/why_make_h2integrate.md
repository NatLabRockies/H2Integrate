# Welcome to H2Integrate

This collection of docs is focused on presenting H2Integrate, acknowledging where we are now and where we want to be in the future.
Most of these docs are written in a way that we'll be able to reuse them immediately as proper docs in the actual H2Integrate repo.
For now, to reduce development overhead and encourage rapid iteration, we'll continue to work in this sandbox repo.

Our goal with these doc pages is to communicate ideas that exist in our heads, put them to paper, and provide diagrams where helpful.
These docs are a work in progress; please ask questions about any and all parts presented here.

## Why make H2Integrate?

H2Integrate has already proven itself useful as a tool that can analyze and design complex hybrid systems producing electricity, hydrogen, steel, and more.
However, these developments came in waves across multiple disparate projects, leading to a sometimes disjointed codebase.
In an effort to streamline and modularize H2Integrate to make it more effective and capable for necessary future studies, we are devoting time to redesigning it from the ground up.
This page discusses some of the high-level decisions and mindsets that we've used throughout this process.

## What does it mean to "modularize" H2Integrate?

Most of the current implementation of H2Integrate assumes that you are modeling a certain hybrid system architecture using a limited number of specific models.
As more projects call for using H2Integrate, we must make it easier to develop and add capability to the tool in a sustainable and clear way.
By making the internal framework of H2Integrate more agnostic to the technologies considered in the hybrid system design, we can allow for more user-defined modularized subsystems to be considered effectively.

Getting into the details, this means creating generalized components that H2Integrate can expect to behave in a certain way.

We introduce the ideas of "converters", which convert one resource into another.
Simple examples of converters include electrolyzers, wind turbines, solar PV panels, and more.
These converters can pass resources to other converters or "storage" components via "transporter" components.

Transporters include hydrogen pipelines, electricity cables, or anything that transports a resource.
In a broad sense, these might include delivery trucks or shipping vessels, though those are more for future consideration.

Storage components include batteries, hydrogen tanks; anything where you store a resource.

By combining instances of these different generalized components, we can study distinct hybrid systems in H2Integrate.
Internally, the H2Integrate framework just needs to know if a something is a converter, transporter, storage, or some other type of component.
Additionally, this allows users to develop their own components using the expected interface, and add in custom subsystems to their hybrid plant.

## Why use OpenMDAO as the internal framework for H2Integrate?

Through a series of internal discussions, the H2Integrate dev team landed on using [NASA's OpenMDAO framework](https://github.com/OpenMDAO/OpenMDAO/) for this new version of the tool.

Using OpenMDAO for this gives quite a few benefits:
- a proven framework for complex data-passing within multidisciplinary systems
- automatically-generated visualization tools to help understand models and debug them
- internal units handling and conversion
- built-in nonlinear solvers to resolve model coupling
- built-in optimization and parameter sweep drivers
- multiple existing NLR tools use OpenMDAO, including [WISDEM](https://github.com/NLRWindSystems/WISDEM/) and [WEIS](https://github.com/NLRWindSystems/WEIS), so we can draw from institutional knowledge
- set up with gradient-based optimization in mind, which is not currently a focus for H2Integrate but this positions the tool well for potential future additions
- parallelization done using MPI, which is also not currently a focus but useful for the future

However, there are a few downsides to using OpenMDAO:
- an additional layer of code that developers must consider
- longer error stack traces that might seem daunting in the terminal
- potentially increased computational costs depending on problem type and size
- it isn't great at optimizing mixed-integer problems

The benefits outweighed the downsides, hence the team's choice to use OpenMDAO going forward.
Additionally, we can code H2Integrate in a way to minimize some of the potential issues, given that we're aware of them before refactoring H2Integrate.

## Where does HOPP come into play?

[HOPP](https://github.com/NatLabRockies/HOPP) is a well-structured and useful tool that analyzes hybrid plants producing electricity.
H2Integrate historically calls HOPP to obtain the plant's outputted electricity, which is then used downstream to feed into electrolyzers, steel, and other components.
The current setup of H2Integrate largely works in the same way.

The end-goal of H2Integrate is to remove this call to HOPP as a monolith and instead break out the individual technologies so they are all exposed equally to H2Integrate.
This would entail reworking the dispatch implementation so it is controlled by H2Integrate and not by HOPP, which is a non-trivial task.
HOPP would still exist as a standalone tool, but major framework development would be done in H2Integrate.

## Where should code I develop and implement live?

Historically, H2Integrate has been a sort of hybrid itself, where it contains both the tool itself as well as project-specific code.
Additionally, HOPP has been a separate tool that H2Integrate calls to obtain electricity production data and has been developed alongside H2Integrate.
This has led to a somewhat disjointed codebase that is difficult to maintain and understand.

To address this, here are guidelines for where code you develop should live:
- If the code is specific to a project, it should live in the project's repository.
- If the code is generalizable, could be used in multiple projects, or is a useful addition to the H2Integrate tool, it should live in the H2Integrate repository.
- Wrappers to models that are used in H2Integrate should live in the H2Integrate repository.
- The actual models (physics, costs, financials) should live **outside** the H2Integrate repository. Complex models might live in their own repo (e.g. BERT), whereas other models might live in the project's repository.
