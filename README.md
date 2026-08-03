# Martini Force Field Initiative Website

Martini is a coarse-grained force field suited for molecular dynamics simulations of (bio)molecular systems. The Martini Force Field Initiative website, live at [cgmartini.nl](https://cgmartini.nl), serves as a central hub for the Martini community, providing resources, publications, tutorials, and tools to facilitate the use and development of the Martini force field.

## Repository Layout

| Path | Contents |
|---|---|
| `docs/publications/` | One `.qmd` per paper, filed by year under `entries/` |
| `docs/announcements/` | One folder per post under `posts/`; `_metadata.yml` is generated |
| `docs/tutorials/Martini3/` | One folder per tutorial, listed in `tutorials.qmd` |
| `docs/downloads/` | Tools, force-field parameters, example inputs |
| `scripts/validate/` | The contribution validator: schemas, rules, tests |

## How to Contribute

We welcome contributions from the community and appreciate your efforts to improve and expand the Martini Force Field Initiative website! This guide walks through setting up your environment, making your changes, validating them locally, and submitting a pull request for review.

## Common Commands

Everything a contributor needs is a `make` target. Run `make help` to list them.

| Command | What it does |
|---|---|
| `make setup` | Create `.venv` with the one Python dependency (PyYAML) |
| `make preview` | Serve the site locally on <http://localhost:4040> |
| `make validate` | Check every contribution against its validation rules |
| `make lint-itp FILES="…"` | Lint Martini `.itp` topologies anywhere on disk |
| `make metadata` | Regenerate the homepage news feed from the announcement posts |
| `make links` | Also check that external and download links resolve |
| `make render` | Build the site once into `_site/` |

> **Before you open a pull request**, run `make validate`. Every contribution
> type is checked automatically against a declared se of validation rules. See [Validating Your Changes](#3-validating-your-changes)
> for what is checked and how to read a failure.

### Table of Contents
1. [Setting Up Your Environment](#1-setting-up-your-environment)
    1. [Install Quarto](#11-install-quarto)
    1. [Fork the Repository](#12-fork-the-repository)
    1. [Clone the Repository to your local workstation](#13-clone-the-repository-to-your-local-workstation)
    1. [Set Up the Validator](#14-set-up-the-validator)
1. [Types of Contributions](#2-types-of-contributions)
    1. [Adding New Publications](#21-adding-new-publications)
    1. [Adding New Announcements](#22-adding-new-announcements)
    1. [Adding New Martini 3 Tutorials](#23-adding-new-martini-3-tutorials)
    1. [Adding Tools](#24-adding-tools)
    1. [Adding New Parameter Files](#25-adding-new-parameter-files)
    1. [General Website Enhancements](#26-general-website-enhancements)
1. [Validating Your Changes](#3-validating-your-changes)
    1. [What Gets Checked](#31-what-gets-checked)
    1. [Errors and Warnings](#32-errors-and-warnings)
1. [Submitting a Pull Request](#4-submitting-a-pull-request)
1. [Reviewing and Merging](#5-reviewing-and-merging)
1. [Additional Resources](#6-additional-resources)

### 1. Setting Up Your Environment

You need [Quarto](https://quarto.org) to build and preview the site, and Python 3.9 or newer with PyYAML to run the validator. Nothing else.

#### 1.1. Install Quarto

Follow the instructions below based on your operating system:

* **Windows**:
    1. Download the `.msi` file from the official website [[here]](https://quarto.org/docs/get-started/).
    1. Run the installer and follow the prompts.

* **macOS**:
    1. Download the `.dmg` file from the official website [[here]](https://quarto.org/docs/get-started/).
    1. Open the file and drag Quarto to your Applications folder.

* **Ubuntu/Debian**:
    1. Download the *amd64* `.deb` file from the official website [[here]](https://quarto.org/docs/get-started/).
    1. Complete the installation by running the following command in your terminal:
        ```bash
        sudo dpkg -i quarto-*-linux-amd64.deb
        ```

* **Other Linux Distributions**:
    1. Download the `.tar.gz` file from the official website [[here]](https://quarto.org/docs/get-started/).
    1. Extract the archive and move the `quarto` binary to a directory in your `PATH`.

After installation, verify it by running `quarto check` in your terminal.

#### 1.2. Fork the Repository

Navigate to [this GitHub repository](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io) and click on the ***Fork*** button in the top-right corner of the page to create your own copy.

#### 1.3. Clone the Repository to your local workstation

Clone your fork to your local workstation using the following commands:

```bash
git clone https://github.com/your-username/Martini-Force-Field-Initiative.github.io.git
cd Martini-Force-Field-Initiative.github.io/
```

#### 1.4. Set Up the Validator

In most cases the validator runs straight away. If you get
`ModuleNotFoundError: No module named 'yaml'`, or if `pip install pyyaml`
refuses with `externally-managed-environment` (usual on macOS and recent Linux
distributions), run:

```bash
make setup     # creates .venv with PyYAML; make picks it up automatically
```

Optionally, run the same checks on every commit:

```bash
pip install pre-commit && pre-commit install
```

This is never required, CI will run the validator regardless. It simply surfaces problems before a push rather than after.

### 2. Types of Contributions

There are six main types of contributions you can make to the website. Each one has a matching form under [**Issues → New issue**](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/issues/new/choose).

Whichever type you pick, the last three steps are always the same, so they are not repeated below:

1. Preview locally with `make preview` and open <http://localhost:4040> to check that your change appears as expected.
1. Run `make validate` and fix any errors — see [Validating Your Changes](#3-validating-your-changes).
1. Commit, push, and open a pull request — see [Submitting a Pull Request](#4-submitting-a-pull-request).

#### 2.1. Adding New Publications

1. Navigate to [docs/publications/entry_template.qmd](docs/publications/entry_template.qmd).
1. Copy the template file to the appropriate folder by year under `docs/publications/entries/`, and rename it with a unique identifier, e.g., `author-first_word_in_title.qmd`.
1. Fill in the required fields in the template. The attributes in the header are self-explanatory, and the content should follow best-practice Markdown syntax.
1. Verify the entry appears in the `Publications` section of the local preview.

##### Adding a publication category

Categories are the filter tags on the Publications page, so an ad-hoc synonym makes the filter worse for everyone. The validator warns on any term not in [`scripts/validate/schemas/vocab/publication-categories.yml`](scripts/validate/schemas/vocab/publication-categories.yml) and suggests the closest existing one. If your paper genuinely needs a new term, add one line to that file in the same pull request. The publications editors will review it along with the entry.

#### 2.2. Adding New Announcements

1. Navigate to [docs/announcements/entry_template.qmd](docs/announcements/entry_template.qmd).
1. Copy the template file to the `docs/announcements/posts/` directory and place it in a new folder with a descriptive name including the date and some keywords in the announcement, e.g., `YYYY-MM-DD-keywords/`. We recommend naming the file inside the folder as `index.qmd`, but you can choose a different name of your preference.
1. Complete the template with the relevant details for your announcement.
1. Run `make metadata` and commit the regenerated `docs/announcements/posts/_metadata.yml`. This file drives the homepage news feed; CI fails if it does not match the posts.
1. Verify the announcement is displayed correctly in the `Announcements` section of the local preview.

#### 2.3. Adding New Martini 3 Tutorials

1. Refer to the `index.qmd` file in any of the existing tutorials in `docs/tutorials/Martini3/` as reference, e.g., [docs/tutorials/Martini3/LipidsI/index.qmd](docs/tutorials/Martini3/LipidsI/index.qmd).
1. Create a new tutorial by following the structure and format used in the examples.
1. Place the new tutorial in a dedicated directory under `docs/tutorials/Martini3/`. You can name the directory based on the tutorial topic and application. All the related files (images, data, etc.) should be placed in this directory.
1. Open the file that keeps track of all the tutorials, [`docs/tutorials/Martini3/tutorials.qmd`](docs/tutorials/Martini3/tutorials.qmd), and add a new entry for your tutorial following the same Markdown syntax as the other entries in the list.
1. Verify in the local preview that the tutorial is correctly formatted and reachable from the tutorials page.

#### 2.4. Adding Tools

1. Include the description of your tool in one of the existing `.qmd` files under `docs/downloads/tools/`.
1. Current subsections for *Actively Maintained* tools are `Topology/Structure generation` ([topology-structure-generation.qmd](docs/downloads/tools/topology-structure-generation.qmd)), `Multiscaling` ([multiscaling.qmd](docs/downloads/tools/multiscaling.qmd)), and `Analysis` ([analysis.qmd](docs/downloads/tools/analysis.qmd)). Tools that are no longer maintained live in [legacy.qmd](docs/downloads/tools/legacy.qmd).
1. Verify the tool has integrated seamlessly into the `Downloads/Tools/` section of the local preview.

#### 2.5. Adding New Parameter Files

1. Add the description for the new parameters in the appropriate `.qmd` file in `docs/downloads/force-field-parameters/martini3/`, choosing the molecule type that best fits your case.
1. Share the `.itp` file(s) with the parameters editors. They are **not** added to this repository — they live in the Martini download library, and the editors publish them there once the parameters are approved. Open the [Force-field parameters](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/issues/new?template=05-force-field-parameters.yml) issue form and give a link to a shared location or a repository where the files can be reviewed, along with the molecule names, Martini version, reference DOI, and what you validated the parameters against. If you are also opening a pull request for the description page, link the issue from it.
1. Verify the description shows correctly under `Downloads/Force field parameters/Martini 3/` in the local preview.

Before sharing the files, lint them — they can be anywhere on disk:

```bash
make lint-itp FILES="path/to/martini_MOL.itp"
```

This checks section grammar, atom numbering, bead types against the Martini 3
naming scheme, bonded indices within range, duplicate or self-bonded pairs,
pairs given both a bond and a constraint, non-integral net charge, and
fragments disconnected from the rest of the molecule.


#### 2.6. General Website Enhancements

We also welcome contributions that improve the overall appearance or functionality of the website:

1. Familiarize yourself with the code in [this repository](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/tree/main), see [Repository Layout](#repository-layout) for where things live.
1. Implement your changes.
1. Test extensively in the local preview to ensure no existing functionality is broken. `make render` builds the whole site if you need to check something the preview server does not show.

### 3. Validating Your Changes

Whatever you contributed, run the checks before you push:

```bash
make validate          # check everything
make validate-changed  # check only what you changed against main
make preview           # serve the site at http://localhost:4040
```

`make validate` runs exactly what CI runs. Catching a problem here is cheaper
for everyone than catching it in review. If the validator cannot start because
PyYAML is missing, see [Set Up the Validator](#14-set-up-the-validator).

#### 3.1. What Gets Checked

Every contribution type has a declared contract:

| Type | Contract |
|---|---|
| Publications | [`scripts/validate/schemas/publication.yml`](scripts/validate/schemas/publication.yml) |
| Announcements | [`scripts/validate/schemas/announcement.yml`](scripts/validate/schemas/announcement.yml) |
| Tutorials, tools | structural rules in [`scripts/validate/rules/structure.py`](scripts/validate/rules/structure.py) |
| Force-field parameters | the download pages, via the site-wide rules; the `.itp` files themselves through [`make lint-itp`](#25-adding-new-parameter-files) |
| Site-wide | [`scripts/validate/rules/site.py`](scripts/validate/rules/site.py) |

The schemas are plain YAML on purpose. Adding a field, tightening a format, or
extending the list of publication categories is a one-line edit that a
maintainer can make without touching Python.

The `.itp` linter sits outside `make validate` for a reason: parameter files are
never in this repository, so there is nothing for CI to check. It runs on demand
instead — see [`scripts/validate/core/itp.py`](scripts/validate/core/itp.py) for
what it looks at.

#### 3.2. Errors and Warnings

**Errors** block the merge. Each one corresponds to something that is broken
for readers: a page missing from navigation, a download link pointing at a file
that is not there, an announcement that would never be emailed.

**Warnings** do not block. They flag drift worth a human decision — a new
publication category, a tutorial not yet listed on the tutorials page, a date
in the folder name that disagrees with the date in the post.

Failures appear as annotations on the exact line in the pull-request diff.
Every error also carries a suggested fix.


### 4. Submitting a Pull Request

Once your changes are ready and `make validate` is clean:

1. Commit your changes:
    ```bash
    git add .
    git commit -m "Brief description of your changes"
    ```
1. Push to your fork:
    ```bash
    git push origin your-branch-name
    ```
1. Open the pull request:

    i- Go to your own copy of the repository on GitHub.

    ii- Click the ***Contribute*** button right below the name of your recently pushed branch.

    iii- Click on ***Open pull request*** and fill in the pull request template, which asks you to confirm you previewed the change and that `make validate` reports no errors.

    iv- Submit the pull request.

### 5. Reviewing and Merging

Reviewers are requested automatically based on what you touched — publications, announcements, tutorials, tools, and parameters each have their own editors, as set out in [`.github/CODEOWNERS`](.github/CODEOWNERS). We may request or suggest additional changes, or approve directly. Once approved, your changes are merged into `main`, and the website is re-validated, rebuilt, and deployed automatically by a GitHub Action.

### 6. Additional Resources

For further guidance, please refer to the following:
* [Quarto Documentation](https://quarto.org/docs/)
* [GitHub Markdown Guide](https://guides.github.com/features/mastering-markdown/)

If you have any questions or need assistance, feel free to open an issue on GitHub or contact the team through our [Discussion Board](https://github.com/orgs/Martini-Force-Field-Initiative/discussions).

Thank you for your interest in contributing to the Martini Force Field Initiative website!:)
