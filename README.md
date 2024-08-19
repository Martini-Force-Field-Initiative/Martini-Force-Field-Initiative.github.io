# Martini Force Field Initiative Website

Martini is a coarse-grained force field suited for molecular dynamics simulations of biomolecular systems. The Martini Force Field Initiative website serves as a central hub for the Martini community, providing resources, publications, tutorials, and tools to facilitate the use and development of the Martini force field.

## How to Contribute

We welcome contributions from the community and appreciate your efforts to improve and expand the Martini Force Field Initiative website! This guide provides a step-by-step walkthrough of how to contribute, including setting up your environment, making your changes, and submitting them for review.

### 1. Setting Up Your Environment
Before you begin contributing, you need to set up your local environment to work with [Quarto](https://quarto.org) and this repository.

#### 1.1. Install Quarto

To build and preview the website locally, you need to install [Quarto](https://quarto.org). Follow the instructions below based on your operating system:

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
    
After installation, verify the installation by running `quarto check` in your terminal.

#### 1.2. Fork the Repository

Navigate to [this GitHub repository](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io) and click on the ***Fork*** button in the top-right corner of the page to create your own copy.

#### 1.3. Clone the Repository to your local workstation

Clone your fork to your local workstation using the following commands:

```bash
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name
```

### 2. Types of Contributions
There are six main types of contributions you can make to the website:

#### 2.1. Adding New Publications

1. Navigate to [docs/publications/entry_template.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/publications/entry_template.qmd).
1. Copy the template file to the appropriate year folder under `docs/publications/entries/`, and rename it with a unique identifier, e.g., `author-first_word_in_title.qmd`.
1. Fill in the required fields in the template. The headers are self-explanatory, and the content should follow best-practice Markdown syntax.
1. Preview the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Open your browser and navigate to `http://localhost:4040` to verify that the publication has been integrated as expected in the `Publications` section of the website.
1. Once verified, commit your changes and submit a pull request to this repository to be reviewed by the Martini Developers Team.

#### 2.2. Adding New Announcements

1. Navigate to [docs/announcements/entry_template.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/announcements/entry_template.qmd).
1. Copy the template file to the `docs/announcements/posts/` directory and place it in a new folder with a descriptive name including the date and some keywords of the announcements, e.g., `YYYY-MM-DD-keywords/`. We recommend naming the file inside the folder as `index.qmd`, but you can choose a different name if you prefer.
1. Complete the template with the relevant announcement details.
1. Preview the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Open your browser and navigate to `http://localhost:4040` to verify that the announcement is displayed correctly in the `Announcements` section of the website.
1. Once verified, commit your changes and submit a pull request to this repository to be reviewed by the Martini Developers Team.

#### 2.3. Adding New Martini 3 Tutorials

1. Refer to the `index.qmd` file in any of the existing tutorials in `docs/tutorials/Martini3/` as a reference, e.g., [docs/tutorials/Martini3/LipidsI/index.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/tutorials/Martini3/LipidsI/index.qmd).
1. Create a new tutorial by following the structure and format used in the example.
1. Place the new tutorial in a dedicated directory under `docs/tutorials/Martini3/`. You can name the directory based on the tutorial topic and application. All the related files (images, data, etc.) should be placed in this directory.
1. Open the file that keeps track of all the tutorials in [`docs/tutorials/Martini3/tutorials.qmd`](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/tutorials/Martini3/tutorials.qmd) and add a new entry in the list for your tutorial following the same Markdown syntax as the other entries in the file.
1. Preview the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Open your browser and navigate to `http://localhost:4040` to verify that the tutorial is correctly formatted and functional.
1. Once verified, commit your changes and submit a pull request to this repository to be reviewed by the Martini Developers Team.

#### 2.4. Adding Tools

1. Include the description of your tool in one of the existing `.qmd` files under `docs/downloads/tools/`.
1. Current subsections include `Proteins and Bilayers`([proteins-and-bilayers.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/downloads/tools/proteins-and-bilayers.qmd)), `Resolution transformation`([resolution-transformation.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/downloads/tools/resolution-transformation.qmd)), `Visualization`([visualization.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/downloads/tools/visualization.qmd)), and `Other tools`([other-tools.qmd](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/blob/main/docs/downloads/tools/other-tools.qmd)).
1. Preview the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Open your browser and navigate to `http://localhost:4040` to verify that the tool has integrated seamlessly in the `Downloads/Tools/` section of the website.
1. Once verified, commit your changes and submit a pull request to this repository to be reviewed by the Martini Developers Team.

#### 2.5. Adding New Parameter Files

1. Add the description for the new parameters in the appropriate `.qmd` file in `docs/downloads/force-field-parameters/martini3/` attending to the molecule type that better fits your case.
1. Keep your `.itp` parameters files at hand to share them with the Martini Developers Team during the Pull Request and reviewing process. If approved, the files will be included to be directly downloaded from the website.
1. Preview the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Open your browser and navigate to `http://localhost:4040` to verify that the description of the parameters is showing correctly in the subsection at `Downloads/Force field parameters/Martini 3/`, corresponding to the specific molecule type you choose.
1. Once verified, commit your changes and submit a pull request to this repository to be reviewed by the Martini Developers Team.

#### 2.6. General Website Enhancements

We also welcome contributions that improve the overall appearance or functionality of the website. The recommended steps for this type of contribution are as follows:

1. Familiarize yourself with the code in [this repository](https://github.com/Martini-Force-Field-Initiative/Martini-Force-Field-Initiative.github.io/tree/main).
1. Implement your changes.
1. Preview the changes in the website locally using the following command from the root directory of the repository:
    ```bash
    quarto preview --port 4040
    ```
1. Test extensively to ensure no existing functionality is broken.
1. Submit your enhancements via a pull request to this repository to be reviewed by the Martini Developers Team.

### 3. Submitting a Pull Request
Once your changes are ready:

1. Commit Your Changes:
```bash
git add .
git commit -m "Brief description of your changes"
```
2. Push to Your Fork of the Repository:
```bash
git push origin your-branch-name
```
3. Submit a Pull Request:

    i- Go to your repository on GitHub.
    
    ii- Click the ***Compare & pull request*** button next to your recently pushed branch.
    
    iii- Fill in the pull request template with details about your changes.
    
    iv- Submit the pull request.

4. Reviewing and Merging

Your pull request will be reviewed by other users in the Martini Developers Team. We may request changes or approve it directly. Once approved, your changes will be merged into the main branch, and the website will be automatically updated and deployed via a GitHub Action.

5. Additional Resources
For further guidance, please refer to the following:
* [Quarto Documentation](https://quarto.org/docs/)
* [GitHub Markdown Guide](https://guides.github.com/features/mastering-markdown/)

If you have any questions or need assistance, feel free to open an issue on GitHub or contact the team through our [Discussion Board](https://github.com/orgs/Martini-Force-Field-Initiative/discussions).

Thank you for your interest in contributing to the Martini Force Field Initiative website!:)
