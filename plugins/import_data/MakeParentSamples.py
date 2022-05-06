# -*- coding: utf-8 -*-
"""
Created on Fri May  6 08:42:26 2022

@author: Peter
"""

    def split_grain_information(self, df):
        # Really the only way to ID aliquots from larger samples is to use
        # the last few characters separated by a _ or -; if the sample name does not
        # conform to this standard there is no reliable way to do so. This will simply create
        # extraneous samples if there is no "aliquot" information
        # We banish underscores from sample names entirely to split.
        # Only dashes. This simplifies our life tremendously.
        df[["sample_name", "-", "grain"]] = df["Full Sample Name"].str.replace("_","-").str.rpartition("-")
        # Go back to previous separators
        df["sample_name"] = df.apply(lambda row: row["Full Sample Name"][0:len(row["sample_name"])], axis=1)
        df.drop(columns=["-"], inplace=True) # Created a separate column full of "-", which is useless

        # Find the number of grains per sample
        n_grains = df.pivot_table(index=['sample_name'], aggfunc='size')
        singles = df.sample_name.isin(n_grains[n_grains == 1].index)
        df.loc[singles, "sample_name"] = df.loc[singles,"Full Sample Name"]
        df.loc[singles, "grain"] = np.nan

        return df