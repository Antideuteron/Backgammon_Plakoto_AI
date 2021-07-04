"""
Intelligent agent that uses deep Q-learning for learning to play backgammon. 

DQN Details:
    - TODO

TODO
    - DQN class
    - Read up on buffer and change what needs to be changed
    - run on the Stanford VM (1 hour)
    - upload on github
"""

# ------------------------------- Config ---------------------------------

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.models import *
from Backgammon import *

# TODO: make your own or cite the thing
# https://towardsdatascience.com/dqn-part-1-vanilla-deep-q-networks-6eb4a00febfb
# https://github.com/cyoon1729/deep-Q-networks/blob/master/common/replay_buffers.py
from basic_buffer import BasicBuffer 

import Backgammon


# Model config and hyperparameters 
class config:
    nS = 48+1 # state space demension: boardspace + isAnotherMoveComing
    eps = 0.05
    lr = 0.05
    gamma = 0.99
    C = 100
    batch_size = 32
    D_max = 1000

print('Model initialized with parameters:','\n'*2, config, '\n'*2)

# ------------------------------- Model initialization ---------------------------------



# Our deep Q-network
DQN = keras.Sequential([
    layers.Dense(50, activation='relu', kernel_initializer='random_uniform', input_shape=(config.nS,)),
    # layers.Dense(4, activation='relu', kernel_initializer='random_uniform'),
    layers.Dense(1, activation='sigmoid', kernel_initializer='random_uniform')
])
DQN.compile(optimizer = 'Adam',loss = 'mse')

# Target network to stabelize
DQN_target = tf.keras.models.clone_model(DQN) # https://www.tensorflow.org/api_docs/python/tf/keras/models/clone_model
DQN_target.compile(optimizer = 'Adam',loss = 'mse')

#===========================================================

# Our deep Q-network for when wer're bearing off
DQN_bearing_off = tf.keras.models.clone_model(DQN)
DQN_bearing_off.compile(optimizer = 'Adam',loss = 'mse')

# Target network to stabelize
DQN_bearing_off_target = tf.keras.models.clone_model(DQN)
DQN_bearing_off_target.compile(optimizer = 'Adam',loss = 'mse')

# replay buffer to reduce correlation
D = BasicBuffer(config.D_max)
D_bearing_off = BasicBuffer(config.D_max)

# for tracking progress
counter = 0
bearing_off_counter = 0
saved_models = []

print("Network architecture: \n", DQN)

def loadModel(file):
    DQN.load_weights(file)

# ------------------------------- Helper functions ---------------------------------
def pretty_print(board):
    string = str(np.array2string(board[1:13])+'\n'+
                np.array2string(board[24:12:-1])+'\n'+
                np.array2string(board[49:51]))
    print("board: \n", string)

def flip_board(board_copy):
    #flips the game board and returns a new copy
    idx = np.array([0,24,23,22,21,20,19,18,17,16,15,14,13,
    12,11,10,9,8,7,6,5,4,3,2,1,
    48,47,46,45,44,43,42,41,40,39,38,37,
    36,35,34,33,32,31,30,29,28,27,26,25,
    50,49])
    flipped_board = -np.copy(board_copy[idx])
    return flipped_board

def flip_move(move):
    if len(move)!=0:
        for m in move:
            for m_i in range(2):
                #m[m_i] = np.array([0,24,23,22,21,20,19,18,17,16,15,14,13,
                #                12,11,10,9,8,7,6,5,4,3,2,1,26,25,28,27])[m[m_i]]
                m[m_i] = np.array([0,24,23,22,21,20,19,18,17,16,15,14,13,
                        12,11,10,9,8,7,6,5,4,3,2,1,
                        48,47,46,45,44,43,42,41,40,39,38,37,
                        36,35,34,33,32,31,30,29,28,27,26,25,
                        50,49])[m[m_i]]
    return move

board_2_state = lambda board, first_of_2: np.append(board[1:49], first_of_2) #forst_of_two means dice
bearing_off   = lambda board: sum(board[7:25]>0)==0
game_won      = lambda board: int(board[49]>=15 or (board[1+24] == -1 and board[24] <= 0 and board[24+24] != 1))

def game_over_update(board, reward):
    target = np.array([[reward]])
    S = np.array([board_2_state(board, 1)])
    buffer = D if not bearing_off(board) else D_bearing_off
    buffer.push(S, None, reward, S, target, done=True)
    # print("game over update:")
    # Backgammon.pretty_print(board)
    # print("reward: ", reward)

# ------------------------------- Action ---------------------------------

def action(board_copy,dice,player,i,train=False,train_config=None):
    """
    inputs are the board, the dice and which player is to move
    outputs the chosen move accordingly to its policy
    """

    # global variables
    global counter
    global bearing_off_counter

    # starts by flipping the board so that the player always sees himself as player 1
    if player == -1:
        board_copy = flip_board(board_copy)

    # check out the legal moves available for the throw
    possible_moves, possible_boards = Backgammon.legal_moves(board_copy, dice, player=1)

    # if there are no moves available, return an empty move
    if len(possible_moves) == 0:
        return []

    if not bearing_off(board_copy):
        model = DQN
        buffer = D
    else:
        model = DQN_bearing_off
        buffer = D_bearing_off
        bearing_off_counter += 1

    # Current state and Q value, possible next states
    S = np.array([board_2_state(board_copy, i==2)]) #i -> second dice?
    Q = model(S)
    first_of_2 = 1+(dice[0] == dice[1])-i
    S_primes = np.array([board_2_state(b, first_of_2) for b in possible_boards]) #possible next states

    # Find best action and it's q-value w/ epsilon-greedy
    Q_primes = model(S_primes)  # q-value per state
    action = np.argmax(Q_primes)
    if train and np.random.rand() < config.eps: # epsilon-greedy when training
        action = np.random.randint(len(possible_moves))

    # TODO: Fix the 16-piece bug (1 hour)
    # print("action:", action)
    # print("board:")
    # Backgammon.pretty_print(board_copy)
    # print('"endgames":')
    # [Backgammon.pretty_print(b) for b in possible_boards]

    if train:
        # # number of games
        # g = train_config['g']

        # state chosen from eta-greedy
        S_prime = np.array([board_2_state(possible_boards[action], first_of_2)])

        # update Target network
        if not bearing_off(possible_boards[action]):
            target_model = DQN_target
        else:
            target_model = DQN_bearing_off_target
        Q_max = target_model(S_prime)

        #Das Kernstück des ganzen
        reward = game_won(possible_boards[action]) #game won on chosen state?
        target = Q + config.lr*(reward + config.gamma*Q_max - Q)
        buffer.push(S, None, reward, S_prime, target, done=True)

        # update the target network every C steps
        if counter % config.C == 0:
            target_model.set_weights(model.get_weights())

        # train model from buffer
        if counter % config.batch_size == 0 and bearing_off_counter > config.batch_size:
            state_batch, action_batch, reward_batch, next_state_batch, target_batch, done_batch = D.sample(config.batch_size)
            DQN.train_on_batch(np.array(state_batch), np.array(target_batch))
            state_batch, action_batch, reward_batch, next_state_batch, target_batch, done_batch = D_bearing_off.sample(config.batch_size)
            DQN_bearing_off.train_on_batch(np.array(state_batch), np.array(target_batch))

        # save model every 1000_000 training moves
        if counter % 100000 == 0 and not counter in saved_models and counter != 0:
            # save both networks
            filepath = "./kotra_weights/DQN_"+str(counter)
            print("saving weights in file:"+filepath)
            DQN.save(filepath, overwrite=True, include_optimizer=True)

            filepath += "bearing_off"
            print("saving bearing-off-weights in file:"+filepath)
            DQN_bearing_off.save(filepath, overwrite=True, include_optimizer=True)
            saved_models.append(counter)


        counter += 1

    # Make the move
    move = possible_moves[action]

    if player == -1:
        # if the table was flipped the move has to be flipped as well
        move = flip_move(move)

    return move

