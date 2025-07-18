from typing import Dict

import numpy as np
import pandas as pd
from sklearn import linear_model
from sklearn.linear_model._base import LinearModel
from sklearn.metrics import explained_variance_score, r2_score
from sklearn.model_selection import train_test_split

from odusseas.utils import Measurement, Reference, Result


def mean_abso_error(y_true, y_pred):
    return np.mean(np.abs((y_true - y_pred)), axis=0).values


def get_regression_model(name: str) -> LinearModel:
    match name:
        case "linear":
            return linear_model.LinearRegression()
        case "ridge":
            return linear_model.Ridge(alpha=1)
        case "ridgecv":
            return linear_model.RidgeCV(alphas=[0.1, 1.0, 10.0], cv=5, gcv_mode=None)
        case "multitasklasso":
            return linear_model.MultiTaskLasso(alpha=1)
        case "multitaskelasticnet":
            return linear_model.MultiTaskElasticNet(alpha=1)
    raise ValueError(f"Regression '{name}' is not valid")


def ML(spectra: Dict[str, int], regression: str, reference: str) -> None:
    reg = get_regression_model(regression)

    results = []
    for fname, resolution in spectra.items():
        # This is the EW we already measured
        measurement = Measurement(fname, resolution)
        spectrum = measurement.spectrum
        print(f"Getting atmospheric parameters for {spectrum.name} ...")
        newdf = measurement.newdf
        # Get the reference data
        ref = Reference(resolution, reference)
        df_x, df_y = ref.subset_with_wavelengths(newdf.wavelength.values)

        result = Result(
            resolution=str(resolution),
            reference=reference,
            spectrum=spectrum.name,
            params_sub_result={
                "fehs": [],
                "teffs": [],
                "feh_maes": [],
                "teff_maes": [],
                "variances": [],
                "r2scores": [],
            },
        )
        for _ in range(100):
            x_train, x_test, y_train, y_test = train_test_split(
                df_x, df_y, test_size=0.30
            )

            labels_train = y_train[["names"]]
            labels_test = y_test[["names"]]

            y_train.drop(["names"], axis=1, inplace=True)
            y_test.drop(["names"], axis=1, inplace=True)

            reg.fit(x_train.values, y_train)

            y_pred_test = reg.predict(x_test.values)

            variancescore = float(explained_variance_score(y_test, y_pred_test))
            r2score = float(r2_score(y_test, y_pred_test))

            pred_newdf = reg.predict(
                newdf.set_index("wavelength").T
            )  # applying the saved model

            mae_test = mean_abso_error(y_test[:], y_pred_test[:])

            train_givenvalues = pd.concat([labels_train, y_train], axis=1)
            train_givenvalues = train_givenvalues.reset_index(drop=True)

            test_givenvalues = pd.concat([labels_test, y_test], axis=1)
            test_givenvalues = test_givenvalues.reset_index(drop=True)
            new_labeltest = labels_test.reset_index(drop=True)
            test_predvalues = pd.concat(
                [new_labeltest, pd.DataFrame(y_pred_test)], axis=1
            )

            result.params_sub_result["fehs"].append(pred_newdf[0][0])
            result.params_sub_result["teffs"].append(pred_newdf[0][1])
            result.params_sub_result["feh_maes"].append(mae_test[0])
            result.params_sub_result["teff_maes"].append(mae_test[1])
            result.params_sub_result["r2scores"].append(r2score)
            result.params_sub_result["variances"].append(variancescore)

        results.append(result)

    # Save all the results
    with open("Parameter_Results.dat", "w") as fh:
        fh.write(
            "newstars [Fe/H] STD_FeH MAE_[Fe/H] Wide_Error_[Fe/H] Teff STD_Teff MAE_Teff Wide_Error_Teff R2_score EV_score\n"
        )
        for result in results:
            fh.write(str(result))
    print("Results saved to Parameter_Results.dat")
