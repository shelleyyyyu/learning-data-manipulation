import torch
import argparse

from data_utils.data_utils import get_data
from weighting.classifier import Classifier
from weighting.image_classifier import ImageClassifier


device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print('device:', device)

parser = argparse.ArgumentParser()

# data
parser.add_argument('--task', choices=['sst-2', 'sst-5', 'cifar-10'])
parser.add_argument('--train_num_per_class', default=None, type=int)
parser.add_argument('--dev_num_per_class', default=None, type=int)
parser.add_argument('--imbalance_rate', default=1.0, type=float)
parser.add_argument('--data_seed', default=159, type=int)

# training
parser.add_argument('--epochs', default=10, type=int)
parser.add_argument('--min_epochs', default=0, type=int)
parser.add_argument('--pretrain_epochs', default=0, type=int)
parser.add_argument("--learning_rate", default=4e-5, type=float)
parser.add_argument('--batch_size', default=4, type=int)

# weighting
parser.add_argument("--w_decay", default=10., type=float)
parser.add_argument("--w_init", default=0., type=float)
parser.add_argument('--norm_fn', choices=['linear', 'softmax'])

# image
parser.add_argument('--resnet_pretrained', default=False, action='store_true')
parser.add_argument('--image_lr', default=1e-3, type=float)
parser.add_argument('--image_momentum', default=0.9, type=float)
parser.add_argument('--image_weight_decay', default=0.01, type=float)
parser.add_argument('--image_softmax_norm_temp', default=1., type=float)

args = parser.parse_args()
print(args)


def main():
    examples, label_list = get_data(
        task=args.task,
        train_num_per_class=args.train_num_per_class,
        dev_num_per_class=args.dev_num_per_class,
        imbalance_rate=args.imbalance_rate,
        data_seed=args.data_seed)

    if args.task in ['sst-2', 'sst-5']:
        classifier = Classifier(
            label_list=label_list, ren=False, norm_fn=args.norm_fn, device=device)
        classifier.get_optimizer(learning_rate=args.learning_rate)

    else:
        classifier = ImageClassifier(
            pretrained=args.resnet_pretrained,
            norm_fn=args.norm_fn,
            softmax_temp=args.image_softmax_norm_temp)

        classifier.get_optimizer(
            learning_rate=args.image_lr,
            momentum=args.image_momentum,
            weight_decay=args.image_weight_decay)

    for split in ['train', 'dev', 'test']:
        classifier.load_data(
            set_type=split,
            examples=examples[split],
            batch_size=args.batch_size,
            shuffle=(split != 'test'))

    classifier.init_weights(
        n_examples=len(examples['train']),
        w_init=args.w_init,
        w_decay=args.w_decay)

    print('=' * 60, '\n', 'Pre-training', '\n', '=' * 60, sep='')
    for epoch in range(args.pretrain_epochs):
        classifier.pretrain_epoch()
        dev_acc = classifier.evaluate('dev')

        print('Pre-train Epoch {}, Dev Acc: {:.4f}'.format(
            epoch, 100. * dev_acc))

    print('=' * 60, '\n', 'Training', '\n', '=' * 60, sep='')
    best_dev_acc, final_test_acc = -1., -1.
    for epoch in range(args.epochs):
        classifier.train_epoch()
        dev_acc = classifier.evaluate('dev')

        if epoch >= args.min_epochs:
            do_test = (dev_acc > best_dev_acc)
            best_dev_acc = max(best_dev_acc, dev_acc)
        else:
            do_test = False

        print('Epoch {}, Dev Acc: {:.4f}, Best Ever: {:.4f}'.format(
            epoch, 100. * dev_acc, 100. * best_dev_acc))

        if do_test:
            final_test_acc = classifier.evaluate('test')
            print('Test Acc: {:.4f}'.format(100. * final_test_acc))

    print('Final Dev Acc: {:.4f}, Final Test Acc: {:.4f}'.format(
        100. * best_dev_acc, 100. * final_test_acc))


if __name__ == '__main__':
    main()
