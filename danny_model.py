
# coding: utf-8

# # ORIGINAL CODE

#  ## Load the data into a Pandas Dataframe
# 
# ### Point os.walk to the directory that contains all the subdirectories for the batches.

# In[1]:


import os
import numpy as np
import pandas as pd

# Set up lists
t=[]
d=[]
last_packet_time=[]
v_id = []
lengths = []

videos = [0,1,2,3,4,5,6,7,8]
vlengths = [113.000000, 147.000000, 123.000000, 109.000000,
            150.000000, 104.000000, 401.000000, 161.000000, 
            163.000000]

# Read all the files in the directory tree
for subdir, dirs, files in os.walk('/home/carlos.campuzano/Thesis/dataset'): 
    
    for file in files:
        fname = os.path.join(subdir, file)
        times=[]
        directions=[]
    
        with open(fname, 'rb') as f:
            lines = f.readlines()
            #print('Reading file: ', fname)
            for linei in range(0, len(lines)):
                #if number of lines in a file less than a 100
                if len(lines) < 10: #before 100
                    continue
                line = lines[linei]    
                parts = line.strip().split()
                #print('Reading file: ', fname)
                #print(parts)
                try:
                    #more than 100 will be appended to time/directions
                    times.append(float(parts[0]))
                    directions.append(float(parts[1]))
                except IndexError:
                    break
                    #print('Error reading file',fname)
        
        # Append every row:
        if len(times) >= 10:
          
            t.append(times) # times
            d.append(directions) # directions
            last_packet_time.append(times[-1]) # last packet time
            v_id.append(int(file[2:-2])) # video id
            lengths.append(vlengths[int(file[2:-2])]) #last row

# Make same length
length = max(map(len, t))
t=[xi+[None]*(length-len(xi)) for xi in t]
        
length = max(map(len, d))
d=[xi+[None]*(length-len(xi)) for xi in d]

# Create column names
t_names=[]
d_names=[]

for i in range(0,len(t[0])):
    t_names.append('t'+str(i))
    d_names.append('d'+str(i))
    
# Read data into dictionary
pd_dict={}
for i in range(0,len(t)):
    
    if last_packet_time[i] <= lengths[i]:
        continue
        
    # Added to remove packet times with more than 1000
    elif last_packet_time[i] >= 1000:
        continue
    
    pd_dict['row_'+str(i)] = [v_id[i]] + [lengths[i]] + [last_packet_time[i]] + t[i] + d[i]
          
# Create dataframe from dictionary           
df = pd.DataFrame.from_dict(pd_dict, orient='index')
df.columns = ['v_id'] + ['length'] + ['last_packet_time'] + t_names + d_names

df = df.fillna(0)


# In[ ]:


df.head()


# In[ ]:


df.info()


# ## Visualize distributions of features

# In[ ]:


import matplotlib.pyplot as plt
df[['t10','t100','t200','t300','t400','t500','d10','d100','d200','d300','d400','d500']].hist(bins=50, figsize=(15,15))
plt.show()


# ## Scatter plot of last_packet_time vs. length

# In[3]:


c
df.plot(kind="scatter", x='last_packet_time', y='length')#, grid=True)
plt.savefig('NEW.png')


# In[ ]:


df.describe()


# ## Correlation matrix

# In[ ]:


df[['length','last_packet_time','t100','t500','t1000','d100','d500','d1000','v_id']].corr()


# In[ ]:


from pandas.plotting import scatter_matrix
scatter_matrix(df[['length','last_packet_time','t100','t500','t1000','d100','d500','d1000','v_id']], figsize=(16,12),alpha=0.3)


# In[ ]:


import seaborn as sns

sns.heatmap(df[['length','last_packet_time','t100','t500','t1000','d100','d500','d1000','v_id']].corr())
plt.savefig('correlation.png')


# ## Create data set X containing only timing and direction features, and labels y that contain the video id. 

# In[15]:


#ADDDrop time columns
#df = df.loc[:, ~df.columns.str.startswith('t')]

X = df.drop(['v_id','length','last_packet_time'],axis=1)
y_id = df[['length']]


# In[16]:


#import matplotlib.pyplot as plt
X
#plt.savefig('x.png')


# In[17]:


X[X<0] = -1
X[X>0] = 1


# In[18]:


X


# ### df.plot(kind="scatter", x= 'last_packet_time', y='v_id', grid=True)

# ## Scale the features

# In[8]:


from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

pipeline = Pipeline([
                    ('std_scaler', StandardScaler()),
                    ])

df_scaled = pipeline.fit_transform(X)
X = pd.DataFrame(df_scaled)


# In[9]:


X


# ## Split into training and testing sets

# In[ ]:


from sklearn.model_selection import train_test_split
X_train, X_test, y_id_train, y_id_test = train_test_split(X, y_id, test_size=0.2, random_state=42)


# In[ ]:


from sklearn.tree import DecisionTreeClassifier
tree_clf = DecisionTreeClassifier(max_depth=500)
tree_clf.fit(X_train, y_id_train)
y_id_pred = tree_clf.predict(X_test)


# In[ ]:


from sklearn.metrics import classification_report
print(classification_report(y_id_test, y_id_pred))


# In[ ]:


from sklearn.metrics import accuracy_score
accuracy = accuracy_score(y_id_test, y_id_pred)
print("Accuracy score for video ID: %.1f%%" % (accuracy * 100.0))

