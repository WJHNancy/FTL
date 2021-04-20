# FTL
Feature Transfer Learning via Reinforcement Learning for Software Defect Prediction
## 1.Environment Setup
* tensorflow-v: 1.15.5
* numpy-v: 1.18.5
* scikit-learn-v: 0.19.2
* scikit-v: 0.0
* tqdm-v: 4.59.0
* scipy-v: 1.6.1
* pandas-v: 1.2.3
## 2.Dataset
We use two datasets to evaluate FTL, which are PROMISE collected by Jureczko and Madeyski and NASA MDP dataset curated by Shepperd et al. 
* [PROMISE-Jureczko and Madeyski](https://dl.acm.org/doi/abs/10.1145/1868328.1868342)
* [NASA MDP-Shepperd et al.](https://ieeexplore.ieee.org/abstract/document/6464273)

We have provided the downloaded datasets in the PROMISE and NASA MDP folders. Each project has been randomly divided into 5 folds, each fold data contains two file types: .CSV and .ARFF.
## 3.Model Training and Testing
If you want to use our model quickly, first you need to add the 5 fold data of the project to the 'dataset' folder, we use the synapse-1-1 project as an example. Then afem.py is used to train and test the project. When calling the main function, you need to set two parameters as follows,
```python
if __name__ == "__main__":
```
```python
    classifier = 'nb'  # lr, rf
```
```python
    project = 'synapse-1-1'  # the name of the project
```
```python
    for i in range(5):
```
```python
        main(i, project, classifier)
```

You can change the content of 'classifier' and 'project'. There are three choices for 'classifier','nb','lr' and 'rf', which represent Bayesian classifier, logistic regression classifier and random forest classifier respectively. 'Project' is the name of the project.

The results are displayed in the 'out' folder.
## 4.Appendix
Due to the length limitation of the paper, some figures and tables of the results cannot be displayed in the submitted paper. Appendix.pdf contains these results, and the numbers of the figures and tables are the same as those in the paper.

