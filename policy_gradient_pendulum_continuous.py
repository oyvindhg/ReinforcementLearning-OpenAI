import tensorflow as tf
import tensorflow.contrib.slim as slim
import numpy as np
import math


class policy_net():
    def __init__(self, learning_rate, n_states, action_low, action_high, hidden_layer_size):

        # Build the neural network
        self.input = tf.placeholder(shape=[None, n_states], dtype=tf.float32)
        hidden = slim.stack(self.input, slim.fully_connected, hidden_layer_size, activation_fn=tf.nn.relu)
        self.output = slim.fully_connected(hidden, 1, activation_fn=tf.nn.sigmoid)

        # Convert between outputs and sigmoid
        self.action_avg = (action_high + action_low)/2
        self.mean_action = ((self.output - 0.5)*(action_high - action_low) + self.action_avg)[0][0]
        self.action_holder = tf.placeholder(shape=[None], dtype=tf.float32)
        self.action_sigmoid = (self.action_holder - self.action_avg) / (action_high - action_low) + 0.5

        self.reward_holder = tf.placeholder(shape=[None], dtype=tf.float32)

        # Function for calculating loss
        self.cost = -tf.reduce_mean(self.action_sigmoid * tf.log(self.output) + (1 - self.action_sigmoid) * tf.log(1 - self.output))


        #self.cost = -tf.reduce_mean(self.reward_holder*(self.action_sigmoid * tf.log(self.output)
        #                            + (1 - self.action_sigmoid) * tf.log(1 - self.output)))

        # Functions for calculating the gradients
        tvars = tf.trainable_variables()
        self.gradients = tf.gradients(self.cost, tvars)
        self.gradient_holders = []
        for i, var in enumerate(tvars):
            placeholder = tf.placeholder(tf.float32, name=str(i) + '_holder')
            self.gradient_holders.append(placeholder)

        # Update using the gradients
        optimizer = tf.train.AdamOptimizer(learning_rate)
        self.update_batch = optimizer.apply_gradients(zip(self.gradient_holders, tvars))

class value_net():
    def __init__(self, learning_rate, n_states, hidden_layer_size):

        # Build the neural network
        self.input = tf.placeholder(shape=[None, n_states], dtype=tf.float32)
        hidden = slim.stack(self.input, slim.fully_connected, hidden_layer_size, activation_fn=tf.nn.relu)
        self.output = slim.fully_connected(hidden, 1, activation_fn=None)

        # The error function
        self.new_value = tf.placeholder(shape=[None], dtype=tf.float32)
        self.out = tf.reshape(self.output, [-1])
        self.diffs = self.out - self.new_value
        self.cost = tf.reduce_mean(tf.nn.l2_loss(self.diffs))

        # Functions for calculating the gradients
        tvars = tf.trainable_variables()
        self.gradients = tf.gradients(self.cost, tvars)

        # Update using the gradients
        optimizer = tf.train.AdamOptimizer(learning_rate)
        self.update_batch = optimizer.apply_gradients(zip(self.gradients, tvars))

def average_rewards(r):
    """ take 1D float array of rewards and compute discounted reward """
    averaged_r = np.zeros(len(r))
    running_add = 0
    for t in reversed(range(0, len(r))):
        running_add = running_add + r[t]
        averaged_r[t] = running_add / (len(r) - t)
    return averaged_r

def discount_rewards(r, g):
    """ take 1D float array of rewards and compute discounted reward """
    discounted_r = np.zeros(len(r))
    running_add = 0
    for t in reversed(range(0, len(r))):
        running_add = running_add * g + r[t]
        discounted_r[t] = running_add
    return discounted_r

def step_weights(r, g):
    weighted_r = np.zeros(len(r))
    for t in range(0, len(r)):
        weighted_r[t] = r[t] * pow(g, t)
    return weighted_r

def normalize(r):
    mean = r.mean()
    std = r.std()
    normalized_r = (r-mean)/std
    return normalized_r


def run(env, learning_rate, n_states, action_low, action_high, hidden_layer_size, total_episodes, max_steps, ep_per_update, gamma):

    actor = policy_net(learning_rate, n_states, action_low, action_high, hidden_layer_size)

    baseline = value_net(learning_rate, n_states, hidden_layer_size)

    init = tf.global_variables_initializer()
    update_actor = False

    with tf.Session() as sess:

        sess.run(init)

        total_reward = []

        gradBuffer = sess.run(tf.trainable_variables())
        for i, grad in enumerate(gradBuffer):
            gradBuffer[i] = grad * 0

        avg_rewards = []
        var = 1
        ep_count = 0
        #for ep_count in range(1, total_episodes+1):
        while(True):
            ep_count += 1
            #print('ep:', ep_count)

            if ep_count % 100 == 0:
                print('ep:', ep_count)

            obs = env.reset()



            ep_reward = 0
            obs_history = []
            obs_history_actor = []
            action_history = []
            action_history_actor = []
            reward_history = []
            dell_history_actor = []

            #var = max(math.exp(-ep_count / (total_episodes)*4), 0.1)
            #print('var:', var)
            var = 1

            #print('var:', var)

            std_dev = np.sqrt(var)

            for step in range(max_steps):

                obs_history.append(obs)
                # print(obs)
                mean_action = sess.run(actor.mean_action, feed_dict={actor.input: [obs]})

                action = np.random.normal(mean_action, std_dev)
                while action < action_low or action > action_high:
                    action = np.random.normal(mean_action, std_dev)

                #q = sess.run(actor.action_sigmoid, feed_dict={actor.action_holder: [-2]})
                #print(q)


                action_history.append(action)

                #print('mean')
                #print(mean_action)
                #print('action', action)

                obs, reward, done, info = env.step([action])

                if ep_count % 100 == 0:
                    print('mean:', mean_action)
                    print('action:', action)
                    env.render()

                reward_history.append(reward)
                ep_reward += reward

                if done == True:
                    break

            return_history = average_rewards(reward_history)
            obs_history = np.vstack(obs_history)

            value_history = sess.run(baseline.output, feed_dict={baseline.input: obs_history})
            dell_history = return_history - value_history[:][0]

            sess.run(baseline.update_batch, feed_dict={baseline.input: obs_history, baseline.new_value: return_history})

            #if np.mean(dell_history) > 0:
                #print('dell:', np.mean(dell_history))
                #var = abs((1 - learning_rate) * var + learning_rate * pow(np.mean(dell_history), 2))
                #print('var:', var)

            # print('rewards:', reward_history)
            # print('returns:', return_history)
            # print('value:', value_history)
            # print('dell:', dell_history)

            update_buffer = False
            for i, dell in enumerate(dell_history):
                if dell > 0:
                    #print(i)
                    action_history_actor.append(action_history[i])
                    obs_history_actor.append(obs_history[i])
                    dell_history_actor.append(dell)

                    # print('mean_action:', sess.run(actor.mean_action, feed_dict={actor.input: [obs_history[i]]}))
                    # print('value:', value_history[i])
                    # print('action:', action_history[i])
                    # print('dell: ', dell)

                    #print('state:', obs_history[i])
                    #print('action:', action_history[i])

                    update_buffer = True
                    update_actor = True

            if update_buffer:
                feed_dict={actor.action_holder: action_history_actor,
                           actor.input: obs_history_actor}
                           #actor.reward_holder: dell_history_actor} #This one not really.

                grads = sess.run(actor.gradients, feed_dict=feed_dict)

                for i, grad in enumerate(grads):
                    gradBuffer[i] += grad


            if ep_count % ep_per_update == 0 and update_actor:
                feed_dict = dict(zip(actor.gradient_holders, gradBuffer))
                sess.run(actor.update_batch, feed_dict=feed_dict)

                update_actor = False
                for i, grad in enumerate(gradBuffer):
                    gradBuffer[i] = grad * 0


            total_reward.append(ep_reward)

            if ep_count % 10 == 0:
                avg_rewards.append(np.mean(total_reward[-10:]))
                print('reward:', np.mean(total_reward[-10:]))

        return avg_rewards