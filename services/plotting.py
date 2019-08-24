import datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def balance_graph(users):

    fig, ax = plt.subplots()
    ax.set_ylabel('balance')
    ax.set_title('Balance History')

    for user in users:    
        x = [history.date_created for history in user.balance_histories] 
        y = [history.balance for history in user.balance_histories] 

        ax.plot(x, y, markerfacecolor='CornflowerBlue', markeredgecolor='white', label=user.short_name())
    ax.legend()
    fig.autofmt_xdate()

    return fig.savefig("tmp/balance.png")

