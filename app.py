import streamlit as st
import firebase_admin
from firebase_admin import credentials, db
from firebase_admin.exceptions import FirebaseError
import pandas as pd
import sys
import matplotlib.pyplot as plt
# Initialize Firebase
def init_firebase():
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate("expensetracker-greatmonkey-firebase-adminsdk.json")
            firebase_admin.initialize_app(cred, {
                'databaseURL': 'https://expensetracker-greatmonkey-default-rtdb.firebaseio.com/'
            })
    except FirebaseError as e:
        st.error(f"Failed to initialize Firebase: {str(e)}")

init_firebase()

# Firebase database reference
users_ref = db.reference("users")

# Helper functions
def create_user(username, password):
    user_id = username.lower()
    try:
        if users_ref.child(user_id).get():
            return None, "User already exists!"
        users_ref.child(user_id).set({
            "username": username,
            "password": password,
            "monthlySalary": 0,
            "expenseChart": {}
        })
        return user_id, "Account created successfully!"
    except FirebaseError as e:
        return None, f"Error creating user: {str(e)}"

def authenticate_user(username, password):
    user_id = username.lower()
    try:
        user = users_ref.child(user_id).get()
        if user and user.get('password') == password:
            return user, "Login successful!"
        else:
            return None, "Incorrect username or password."
    except FirebaseError as e:
        return None, f"Error authenticating user: {str(e)}"

def update_expense_chart(user_id, category, budget, spent=0):
    if not category.strip():  # Check for empty category name
        st.error("Category name cannot be empty.")
        return
    try:
        users_ref.child(user_id).child("expenseChart").child(category).set({
            "budget": budget,
            "spent": spent
        })
    except FirebaseError as e:
        st.error(f"Error updating expense chart: {str(e)}")

def add_expense(user_id, category, amount, date):
    try:
        user = users_ref.child(user_id).get()
        if not user:
            st.error("User not found.")
            return

        expense_chart = user.get("expenseChart", {})
        if category in expense_chart:
            new_spent = expense_chart[category]["spent"] + amount
            # Save expense with date as part of an expense log (for tracking multiple expenses)
            expense_log = expense_chart.get(category).get("log", [])
            expense_log.append({"amount": amount, "date": date.strftime("%Y-%m-%d")})

            users_ref.child(user_id).child("expenseChart").child(category).update({
                "spent": new_spent,
                "log": expense_log
            })
    except FirebaseError as e:
        st.error(f"Error adding expense: {str(e)}")

# Page functions
def login_signup_page():
    st.header("Login/Signup")
    login_tab, signup_tab = st.tabs(["Login", "Signup"])

    with login_tab:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user, message = authenticate_user(username, password)
            if user:
                st.session_state["user_id"] = username.lower()
                st.session_state.page = "Dashboard"
                # st.experimental_rerun()
            else:
                st.error(message)

    with signup_tab:
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        if st.button("Sign Up"):
            user_id, message = create_user(new_username, new_password)
            if user_id:
                st.success(message)
            else:
                st.error(message)

def dashboard_page():
    user_id = st.session_state["user_id"]
    st.header(f"{user_id.capitalize()}'s Dashboard")

    # Retrieve user data
    user_data = users_ref.child(user_id).get()
    if not user_data:
        st.error("User data not found.")
        return

    monthly_salary = user_data.get("monthlySalary", 0)
    expense_chart = user_data.get("expenseChart", {})

    # Calculate total spent and remaining balance
    total_spent = sum(category["spent"] for category in expense_chart.values())
    total_remaining = monthly_salary - total_spent

    # Display balances
    st.subheader("Overall Balance Summary")
    st.write(f"**Total Monthly Budget:** ${monthly_salary}")
    st.write(f"**Total Remaining Balance:** ${total_remaining}")

    # Individual category balances
    st.subheader("Category-wise Balance")
    for category, values in expense_chart.items():
        remaining_balance = values["budget"] - values["spent"]
        st.write(f"{category}: **Remaining:** ${remaining_balance} / **Budget:** ${values['budget']}")

    if expense_chart:
        data = {"Category": [], "Spent": [], "Budget": []}
        for category, values in expense_chart.items():
            data["Category"].append(category)
            data["Spent"].append(values["spent"])
            data["Budget"].append(values["budget"])
        
        df = pd.DataFrame(data)

        # Display Bar Chart for Budget vs Spent
        st.subheader("Budget vs Spent by Category")
        st.bar_chart(df.set_index("Category"))

        # Display Pie Chart for Budget Distribution
        st.subheader("Budget Allocation by Category")
        fig1, ax1 = plt.subplots()
        ax1.pie(df['Budget'], labels=df['Category'], autopct='%1.1f%%', startangle=90)
        ax1.axis('equal')  # Equal aspect ratio ensures that pie chart is circular.
        st.pyplot(fig1)

        # Line Plot for Expense Trend Over Time (Dummy Data for Demo)
        st.subheader("Expense Trend Over Time")
        dates = pd.date_range(start="2023-01-01", periods=len(df), freq='M')
        expenses_over_time = [sum(df["Spent"][:i]) for i in range(1, len(df)+1)]
        plt.figure(figsize=(10, 4))
        plt.plot(dates, expenses_over_time, marker='o', color='b')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Expenses')
        st.pyplot(plt)

    else:
        st.write("No budget entries yet. Please set up a budget in the Setup Budget section.")


def add_expense_page():
    user_id = st.session_state["user_id"]
    st.header("Add Expense")
    
    user_data = users_ref.child(user_id).get()
    if not user_data:
        st.error("User data not found.")
        return

    expense_chart = user_data.get("expenseChart", {})
    
    if expense_chart:
        expense_category = st.selectbox("Category", options=expense_chart.keys())
        expense_amount = st.number_input("Amount", min_value=0)
        expense_date = st.date_input("Date")
        
        if st.button("Add Expense"):
            add_expense(user_id, expense_category, expense_amount, expense_date)
            st.success(f"Added expense of {expense_amount} to {expense_category}")
    else:
        st.write("No categories available. Please set up a budget first.")

def setup_budget_page():
    user_id = st.session_state["user_id"]
    st.header("Set Up Monthly Budget")

    monthly_salary = st.number_input("Enter Monthly Salary", min_value=0)
    if st.button("Save Monthly Salary"):
        try:
            users_ref.child(user_id).update({"monthlySalary": monthly_salary})
            st.success("Monthly salary updated.")
        except FirebaseError as e:
            st.error(f"Error saving monthly salary: {str(e)}")

    category = st.text_input("Category")
    budget = st.number_input("Budget", min_value=0)
    if st.button("Add Category"):
        if category:
            update_expense_chart(user_id, category, budget)
            st.success(f"Category '{category}' added with a budget of {budget}")
        else:
            st.error("Category cannot be empty.")

# Main App with Sidebar Navigation
if "user_id" not in st.session_state:
    login_signup_page()
else:
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Dashboard", "Add Expense", "Setup Budget"])
    
    # Update session state with the selected page
    st.session_state.page = page

    # Display the selected page
    if st.session_state.page == "Dashboard":
        dashboard_page()
    elif st.session_state.page == "Add Expense":
        add_expense_page()
    elif st.session_state.page == "Setup Budget":
        setup_budget_page()
