.. _example:

Examples
========

We provide a collection of example notebooks to get a better idea of how to
use pyPESTO, and illustrate core features.

The notebooks can be run locally with an installation of jupyter
(``pip install jupyter``), or online on Google Colab or nbviewer, following
the links at the top of each notebook.
At least an installation of pyPESTO is required, which can be performed by

.. code:: sh

   # install if not done yet
   !pip install pypesto --quiet

Potentially, further dependencies may be required.


Getting started
---------------

.. toctree::
   :maxdepth: 2

   example/getting_started.ipynb
   example/custom_objective_function.ipynb

PEtab and AMICI
---------------

.. toctree::
   :maxdepth: 2

   example/amici.ipynb
   example/petab_import.ipynb

Algorithms and features
-----------------------

.. toctree::
   :maxdepth: 2

   example/fixed_parameters.ipynb
   example/prior_definition.ipynb
   example/sampler_study.ipynb
   example/sampling_diagnostics.ipynb
   example/store.ipynb
   example/history_usage.ipynb
   example/model_selection.ipynb
   example/model_evidence_and_bayes_factors.ipynb
   example/julia.ipynb
   example/relative_data.ipynb
   example/ordinal_data.ipynb
   example/censored_data.ipynb
   example/semiquantitative_data.ipynb
   example/roadrunner.ipynb
   example/gradient_check.ipynb

Application examples
--------------------

.. toctree::
   :maxdepth: 2

   example/conversion_reaction.ipynb
   example/synthetic_data.ipynb
