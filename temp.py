def convert_QTOILD_to_dailycum(df_copy_copy):
    df_copy['Timestamp'] = pd.to_datetime(df_copy['Timestamp'])
    df_copy = df_copy.sort_values(by='Timestamp')
    df_copy['Diff'] = df_copy['HT1 Oil Cum.'].diff()
    reset_points = df_copy['Diff'] < 0
    df_copy.loc[reset_points, 'Diff'] = df_copy.loc[reset_points, 'HT1 Oil Cum.']
    df_copy.loc[~reset_points & (df_copy['Diff'] <= 0), 'Diff'] = 0
    df_copy = df_copy.groupby(df_copy['Timestamp'].dt.date)['Diff'].sum().reset_index(name='HT1 Oil Daily Cum.')
    return df_copy