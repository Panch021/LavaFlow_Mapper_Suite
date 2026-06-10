---
title: 'LavaFlow Mapper Suite: a collection of Python modules for monitoring lava flow propagation in near-real-time from space'
tags:
  - Python
  - Volcanology
  - Remote Sensing
  - Lava flows
  - Near-real-time monitoring
authors:
  - name: Francisco J. Vasconez
    orcid: 0000-0003-2000-1636
    affiliation: 1 
affiliations:
  - name: Instituto Geofísico, Escuela Politécnica Nacional, Quito, Ecuador
    index: 1
date: 26 June 2026
bibliography: paper.bib
---

# Summary

LavaFlow Mapper Suite is an open-source collection of Python modules designed to automate the preliminary mapping and monitoring of active lava flows using thermal satellite observations. The software builds upon and extends the methodology proposed by @Vasconez2022a, integrating data acquisition, visualization, analysis, and reporting tools within a single graphical user interface (GUI). Its primary objective is to support near-real-time monitoring of lava-flow propagation using thermal anomalies detected by the VIIRS and MODIS satellite sensors, which provide multiple observations per day over active volcanic regions worldwide.

By combining automated processing workflows with satellite-derived thermal anomaly datasets, the software enables users to rapidly generate preliminary lava-flow maps, quantify flow propagation, estimate maximum runout distances and propagation rates, visualize eruption evolution through time, and produce standardized reports. These capabilities support hazard assessment and emergency response during effusive eruptions and are particularly valuable for volcano observatories, civil-protection agencies, researchers, and communities exposed to volcanic hazards.

# Statement of Need

During effusive volcanic eruptions, tracking the location, extent, and advancement of active lava flows is essential for hazard assessment and the timely dissemination of information to emergency managers, civil protection agencies, and communities at risk. Up-to-date maps of lava inundation are critical for evaluating potential impacts on infrastructure, population centres, transportation networks, and natural resources. However, obtaining such information in near-real-time remains a challenge, particularly during prolonged crises or at remote volcanoes where field observations and ground-based monitoring data may be limited or unavailable.

Traditionally, lava-flow mapping has relied on field observations, manual interpretation of satellite imagery, or airborne surveys. While field campaigns can provide highly detailed information, they often expose personnel to hazardous conditions and may be logistically difficult or impossible during active eruptions. More recently, thermal surveys conducted from aircraft and unmanned aerial systems (UAS) have proven highly effective for delineating active lava flows and identifying flow-front advancement [@Dietterich2021; @Pedersen2022; @Hrysiewicz2025; @Zoeller2020]. Nevertheless, these approaches require specialized equipment, trained personnel, and significant financial resources, making them inaccessible for many volcano observatories, particularly in developing countries or during rapidly evolving crises.

In this context, satellite-based thermal observations have become a cornerstone of modern volcano monitoring [@Poland2015; @Coppola2025a]. Space-borne sensors provide systematic, repeatable, and globally available observations that enable continuous monitoring of volcanic activity across a wide range of temporal and spatial scales. For example, the MSI and OLI instruments aboard the Sentinel-2 and Landsat missions provide imagery every 5–7 days at spatial resolutions of 20 m and 30 m, respectively. Complementarily, the VIIRS (375 m) and MODIS (1 km) sensors aboard the Suomi-NPP, NOAA-20, NOAA-21, AQUA, and TERRA satellites acquire observations of the same area up to several times per day, providing a unique capability for near-real-time detection of thermal anomalies associated with active lava flows.

The use of satellite thermal data has expanded significantly over the last decade and has become an indispensable tool for monitoring effusive eruptions worldwide. Thermal anomaly datasets have been successfully employed to detect early signs of volcanic unrest [@Laiolo2017; @Girona2021; @Aveni2025], monitor eruption evolution, estimate lava effusion rates, calculate erupted volumes, and map the spatial extent of lava flows [@Blackett2015; @Harris2017; @Marchese2019; @Naismith2019; @Bernard2019; @Walter2019; @Plank2019; @Genzano2020; @Coppola2020; @Coppola2022; @Coppola2025a; @Coppola2025b; @Musacchio2021; @Vasconez2022b]. Despite the increasing availability of thermal anomaly products, transforming these datasets into operational mapping products often requires specialized knowledge in remote sensing, programming, and geospatial analysis, creating a barrier for many end users.

LavaFlow Mapper Suite addresses this gap by providing an integrated, user-friendly platform for the rapid mapping and analysis of active lava flows using thermal anomaly data distributed by [FIRMS](https://firms.modaps.eosdis.nasa.gov/). The software leverages the high temporal resolution of the VIIRS and MODIS sensor networks to automatically retrieve near-real-time observations, apply customizable thermal and spatial filters, and generate standardized products that support both operational monitoring and retrospective analyses.

This project builds upon the methodology originally proposed by @Vasconez2022a, which was implemented in R and made available through theghub platform [(link)](https://theghub.org/resources/lavaflowmapper). LavaFlow Mapper Suite expands and modernizes this framework by integrating multiple processing modules into a single graphical user interface, eliminating the need for programming expertise and substantially reducing the time required to produce actionable information. The software enables users to analyse both ongoing eruptions and historical events using FIRMS records available from 2012 to the present, while near-real-time observations can be accessed with a latency of approximately three hours after satellite acquisition.

# State of the Field

Several operational systems currently provide satellite-based thermal monitoring of active volcanoes. Among the most widely used are [MODVOLC](http://modis.higp.hawaii.edu/) which automatically detects volcanic thermal anomalies from MODIS imagery [@Wright2004], and [MIROVA](https://www.mirovaweb.it/NRT/) which provides near-real-time monitoring of volcanic thermal activity and associated volcanic radiative power measurements [@Coppola2016]. These platforms have become fundamental tools for volcano observatories and researchers because they offer continuous, globally available observations of eruptive activity.

Despite their widespread use, these systems are primarily designed to provide standardized monitoring products rather than user-driven analyses. While they efficiently detect and visualize thermal activity, they generally offer limited flexibility for generating customized lava-flow mapping products, evaluating propagation dynamics, applying user-defined filtering criteria, or producing standardized reports tailored to specific hazard-assessment needs. In many cases, users must export the available datasets and perform additional processing using GIS software, programming tools, or bespoke workflows.

LavaFlow Mapper Suite was developed as a complementary tool rather than a replacement for existing monitoring systems. The software builds upon the thermal anomaly products distributed through FIRMS and transforms them into preliminary lava-flow mapping products through a fully integrated workflow. Unlike existing platforms, users can define custom study areas, temporal windows, spatial filters, and thermal thresholds, enabling both retrospective analyses and near-real-time operational monitoring. The software further integrates data retrieval, visualization, propagation analysis, velocity estimation, animation generation, and report creation within a single graphical user interface.

The scholarly contribution of LavaFlow Mapper Suite lies in bridging the gap between thermal anomaly detection and operational lava-flow mapping. By providing an open-source, reproducible, and accessible framework, the software enables a broader community of users to transform satellite-derived thermal observations into actionable hazard-assessment products without requiring advanced expertise in programming, remote sensing, or GIS.

# Software Design

LavaFlow Mapper Suite was designed around three primary objectives: operational simplicity, reproducibility, and accessibility. The software targets users with diverse technical backgrounds, including observatory staff, emergency managers, students, and researchers, many of whom may not possess extensive experience in programming or remote sensing. Consequently, the system was implemented as a graphical user interface that guides users through the complete workflow, from data acquisition to report generation.

A key design decision was to rely on thermal anomaly products distributed through FIRMS rather than higher-spatial-resolution satellite imagery such as Sentinel-2 or Landsat. Although thermal anomalies from VIIRS and MODIS have coarser spatial resolution, they offer substantially higher temporal frequency and near-real-time availability, allowing the software to prioritize rapid situational awareness during volcanic crises. This trade-off favors operational responsiveness over maximum spatial precision.

The software architecture follows a modular workflow in which individual processing stages can be executed independently while maintaining interoperability between modules. This design facilitates reproducibility, simplifies maintenance, and allows future extensions without requiring substantial modifications to the existing framework. Outputs generated by one module can be reused by subsequent analyses, reducing redundant processing and supporting efficient operational workflows.

The package includes eight core modules:

1. **Global Configuration**: defines the volcano of interest, analysis period, processing thresholds, reference points, and geographic features to be displayed throughout the workflow.

2. **FIRMS Download**: retrieves VIIRS and MODIS thermal anomaly data from [FIRMS](https://firms.modaps.eosdis.nasa.gov/download/) using a personal [API key](https://firms.modaps.eosdis.nasa.gov/api/map_key/).

3. **Anomalies Count**: calculates weekly and monthly frequencies of thermal anomalies to characterize temporal activity trends.

4. **FRP Statistics**: evaluates Fire Radiative Power (FRP) distributions and assists users in selecting appropriate filtering thresholds.

5. **LavaFlow Mapper**: generates preliminary maps of thermal anomalies using spatial and thermal filtering criteria and produces associated time-series analyses.

6. **LavaFlow Propagation**: creates animations showing the evolution of thermal anomalies through time.

7. **Propagation Speed**: estimates lava-flow propagation rates by tracking the most distal thermal anomalies.

8. **Export Report**: generates customizable HTML reports containing maps, figures, and statistical analyses.

By integrating these capabilities into a single workflow, the software reduces the time and technical expertise required to generate preliminary lava-flow mapping products and facilitates rapid dissemination of information during volcanic crises.

# Research Impact Statement

The methodology implemented in LavaFlow Mapper Suite originates from the lava-flow mapping framework proposed by @Vasconez2022a and has already been applied to active eruptions in the Galápagos Islands and other volcanic environments worldwide [@Vasconez2022a; @Ramayanti2025]. These studies demonstrated that thermal anomaly datasets can be effectively transformed into rapid assessments of lava-flow propagation and inundation, providing valuable support for volcanic hazard evaluation.

The software was developed within the operational context of the Instituto Geofísico (Ecuador), where rapid interpretation of volcanic activity is essential for hazard communication and decision making. By automating data retrieval, filtering, visualization, and reporting, the software substantially reduces the time required to generate preliminary lava-flow maps compared with traditional manual workflows.

LavaFlow Mapper Suite is distributed as open-source software and relies exclusively on publicly available satellite datasets, facilitating transparency, reproducibility, and independent verification of results. The inclusion of example projects, automated HTML reporting, and a graphical user interface further lowers adoption barriers and promotes broader use by volcano observatories, researchers, students, and civil-protection agencies. By democratizing access to satellite-based lava-flow monitoring techniques, the software has the potential to enhance hazard-assessment capabilities, particularly within institutions that operate with limited personnel, financial resources, or specialized remote-sensing expertise.

# Availability

LavaFlow Mapper Suite is freely available and open-source. It can be downloaded from the GitHub repository available at [https://github.com/Panch021/LavaFlow_Mapper_Suite](https://github.com/Panch021/LavaFlow_Mapper_Suite).

# AI Usage Disclosure

Generative AI tools were used to assist in specific aspects of software development and manuscript preparation. The scientific methodology, software design, implementation strategy, validation, testing, and all volcanological analyses were conceived, developed, and verified by the author.

AI-assisted tools were used to support the translation of code components from R to Python and to facilitate the integration of multiple independent modules into a unified graphical user interface. All AI-generated code suggestions underwent extensive manual review, modification, testing, debugging, and validation prior to inclusion in the final software package.

Additionally, generative AI was used to assist with improving the clarity, grammar, and readability of the manuscript. As the author is not a native English speaker, AI-assisted editing was employed to refine the writing and presentation of the text. All AI-assisted content was carefully reviewed, revised, and approved by the author, who assumes full responsibility for the accuracy, integrity, and originality of both the software and the manuscript.

# Acknowledgements

The author acknowledges the support of the Instituto Geofísico – Escuela Politécnica Nacional (Ecuador). This work was inspired by the Galápagos eruptions that occurred in 2022 and 2024 and developed as part of the monitoring efforts for active volcanism in Ecuador.

# References
